FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy environment file and project code
COPY environment2.yml ./
COPY . /app

# Install build tools for compiling pip packages
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Allow deprecated sklearn shim
ENV SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=true

# Configure conda for better downloads
RUN conda config --set remote_read_timeout_secs 1000 && \
    conda config --set remote_connect_timeout_secs 30 && \
    conda config --set remote_max_retries 10

# Create environment with retry logic
RUN conda env create -f environment2.yml || \
    (conda clean --all -y && conda env create -f environment2.yml) || \
    (sleep 30 && conda env create -f environment2.yml)

# Activate environment by default
SHELL ["conda", "run", "-n", "multisurv", "/bin/bash", "-c"]

# Install Jupyter in the environment
RUN conda install -n multisurv jupyter -y

# Install additional Python packages with retries
RUN conda install -n multisurv -y -c conda-forge openslide openslide-python watermark || \
    (conda clean --all -y && conda install -n multisurv -y -c conda-forge openslide openslide-python watermark)

# Expose port for Jupyter Notebook
EXPOSE 8888

# Generate Jupyter config and set fixed port to prevent auto-port switching
RUN jupyter notebook --generate-config && \
    echo "c.ServerApp.port = 8888" >> /root/.jupyter/jupyter_server_config.py
    
# Launch Jupyter Notebook by default
CMD ["bash", "-c", "source activate multisurv && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root"]