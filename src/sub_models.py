"""MultiSurv sub-models."""

from bisect import bisect_left

import torch
import torch.nn as nn
from torchvision import models

from embrace_net import EmbraceNet
from attention import Attention


def freeze_layers(model, up_to_layer=None):
    if up_to_layer is None:
        return

    # Freeze all parameters
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze layers starting from `up_to_layer`
    unfreeze = False
    for name, child in model.named_children():
        if name == up_to_layer:
            unfreeze = True
        if unfreeze:
            for param in child.parameters():
                param.requires_grad = True



class ResNet(nn.Module):
    def __init__(self):
        super().__init__()
        base_model = models.resnext50_32x4d(pretrained=True)
        self.n_features = base_model.fc.in_features

        # Freeze layers
        freeze_layers(base_model, up_to_layer='layer3')

        # Remove the classifier (last layer)
        self.feature_extractor = nn.Sequential(*list(base_model.children())[:-1])

    def forward(self, x):
        x = self.feature_extractor(x)     # shape: (B, 2048, 1, 1)
        x = x.view(x.size(0), -1)         # shape: (B, 2048)
        return x



class FC(nn.Module):
    """Fully-connected model to generate final output."""
    def __init__(self, in_features, out_features, n_layers, dropout=True,
                 batchnorm=False, scaling_factor=4):
        super().__init__()
        layers = []

        if n_layers == 1:
            layers = layers + self._make_layer(in_features, out_features, dropout, batchnorm)

        elif n_layers == 2:
            hidden = self._pick_n_neurons(in_features)
            hidden = max(hidden, out_features)
            layers = layers + self._make_layer(in_features, hidden, dropout, batchnorm=True)
            layers = layers + self._make_layer(hidden, out_features, dropout, batchnorm)

        elif n_layers > 2:
            hidden = self._pick_n_neurons(in_features) * scaling_factor
            layers = layers + self._make_layer(in_features, hidden, dropout, batchnorm=True)

            for _ in range(n_layers - 2):
                next_hidden = self._pick_n_neurons(hidden)
                next_hidden = max(next_hidden, out_features)
                layers = layers + self._make_layer(hidden, next_hidden, dropout, batchnorm=True)
                hidden = next_hidden

            layers = layers + self._make_layer(hidden, out_features, dropout, batchnorm)

        else:
            raise ValueError('"n_layers" must be positive.')

        self.fc = nn.Sequential(*layers)

    def _make_layer(self, in_features, out_features, dropout, batchnorm):
        layers = []
        if dropout:
            layers.append(nn.Dropout(p=0.5, inplace=False))
        layers.append(nn.Linear(in_features, out_features))
        layers.append(nn.ReLU(inplace=False))
        if batchnorm:
            layers.append(nn.BatchNorm1d(out_features))
        return layers

    def _pick_n_neurons(self, n_features):
        candidates = [128, 256, 512, 1024, 2048, 4096, 8192]
        for size in candidates:
            if size >= n_features:
                return size
        return candidates[-1]

    def forward(self, x):
        return self.fc(x)


class ClinicalNet(nn.Module):
    def __init__(self, output_vector_size, embedding_dims=[
        (32, 16), (2, 1), (9, 5), (3, 2), (3, 2), (3, 2), (16, 8), (10, 5), (21, 11)
    ]):
        super().__init__()

        self.embedding_layers = nn.ModuleList([
            nn.Embedding(num_categories, emb_dim)
            for num_categories, emb_dim in embedding_dims
        ])

        self.n_continuous = 1  # e.g., age_at_diagnosis
        self.total_embedding_dim = sum([emb_dim for _, emb_dim in embedding_dims])
        self.linear_input_dim = self.total_embedding_dim + self.n_continuous

        self.embedding_dropout = nn.Dropout(p=0.5, inplace=False)
        self.bn_layer = nn.BatchNorm1d(self.n_continuous)
        self.linear = nn.Linear(self.linear_input_dim, 256)
        self.output_layer = FC(256, output_vector_size, 1)

    def forward(self, x):
        categorical_x, continuous_x = x

        # Ensure correct types
        categorical_x = categorical_x.to(torch.int64)
        if continuous_x.shape[1] != self.n_continuous:
            raise ValueError(f"Expected {self.n_continuous} continuous feature(s), got {continuous_x.shape[1]}")

        # Embedding for each categorical column
        x_cat = [emb(categorical_x[:, i]) for i, emb in enumerate(self.embedding_layers)]
        x_cat = torch.cat(x_cat, dim=1)
        x_cat = self.embedding_dropout(x_cat)

        # Normalize continuous input
        x_cont = self.bn_layer(continuous_x)

        # Concatenate categorical + continuous
        x = torch.cat([x_cat, x_cont], dim=1)

        # Forward through FC layers
        out = self.output_layer(self.linear(x))
        return out



class CnvNet(nn.Module):
    """Gene copy number variation data extractor."""
    def __init__(self, output_vector_size, embedding_dims=[(3, 2)] * 2000):
        super().__init__()
        self.embedding_layers = nn.ModuleList([nn.Embedding(x, y)
                                               for x, y in embedding_dims])
        n_embeddings = 2 * 2000
        self.fc = FC(in_features=n_embeddings, out_features=output_vector_size,
                     n_layers=5, scaling_factor=1)

    def forward(self, x):
        x = x.to(torch.int64)

        x = [emb_layer(x[:, i])
             for i, emb_layer in enumerate(self.embedding_layers)]
        x = torch.cat(x, 1)
        out = self.fc(x)

        return out

class WsiNet(nn.Module):
    "WSI patch feature extractor and aggregator."
    def __init__(self, output_vector_size):
        super().__init__()
        self.feature_extractor = ResNet()
        self.num_image_features = self.feature_extractor.n_features
        # Multiview WSI patch aggregation
        self.fc = FC(self.num_image_features, output_vector_size , 1)

    def forward(self, x):
        view_pool = []

        # Extract features from each patch
        for v in x:
            v = self.feature_extractor(v)
            v = v.view(v.size(0), self.num_image_features)

            view_pool.append(v)

        # Aggregate features from all patches
        patch_features = torch.stack(view_pool).max(dim=1)[0]

        out = self.fc(patch_features)

        return out


class Fusion(nn.Module):
    "Multimodal data aggregator."
    def __init__(self, method, feature_size, device):
        super().__init__()
        self.method = method
        methods = ['cat', 'max', 'sum', 'prod', 'embrace', 'attention']

        if self.method not in methods:
            raise ValueError('"method" must be one of ', methods)

        if self.method == 'embrace':
            if device is None:
                raise ValueError(
                    '"device" is required if "method" is "embrace"')

            self.embrace = EmbraceNet(device=device)

        if self.method == 'attention':
            if not feature_size:
                raise ValueError(
                    '"feature_size" is required if "method" is "attention"')
            self.attention = Attention(size=feature_size)

    def forward(self, x):
        
        if self.method == 'attention':
            out = self.attention(x)
        elif self.method == 'cat':
            # Concatenate along feature dimension (dim=2)
            out = torch.cat([x[i] for i in range(x.shape[0])], dim=1)
        elif self.method == 'max':
            # Take max across modalities (dim=0), keep batch and feature dims
            out = torch.max(x, dim=0)[0]  # Result: [32, 512]
        elif self.method == 'sum':
            out = torch.sum(x, dim=0)     # Result: [32, 512]
        elif self.method == 'prod':
            out = torch.prod(x, dim=0)    # Result: [32, 512]
        elif self.method == 'embrace':
            out = self.embrace(x)
        else:
            raise ValueError(f"Unknown fusion method: {self.method}")
    
        return out