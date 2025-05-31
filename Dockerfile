FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy environment file and project code
COPY environment2.yml ./
COPY . /app

ENV SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=true


# Create environment
RUN conda env create -f environment2.yml

# Activate environment by default
SHELL ["conda", "run", "-n", "multisurv", "/bin/bash", "-c"]

# Install Jupyter in the environment
RUN conda install -n multisurv jupyter -y

# Expose port for Jupyter Notebook
EXPOSE 8888

# Launch Jupyter Notebook by default
CMD ["conda", "run", "-n", "multisurv", "jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
