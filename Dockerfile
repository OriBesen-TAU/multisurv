FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# Copy environment file and project code
COPY environment.yml ./
COPY . /app

# Create environment
RUN conda env create -f environment.yml

# Activate environment by default
SHELL ["conda", "run", "-n", "multisurv", "/bin/bash", "-c"]

# Install Jupyter in the environment
RUN conda install -n multisurv jupyter -y

# Expose port for Jupyter Notebook
EXPOSE 8888

# Launch Jupyter Notebook by default
CMD ["conda", "run", "-n", "multisurv", "jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
