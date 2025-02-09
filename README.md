### Create environment from scratch

For WSL: https://gist.github.com/kauffmanes/5e74916617f9993bc3479f401dfec7da

```bash
conda create -n fastapi python=3.11
conda activate fastapi
conda install -c conda-forge poetry
conda env export > environment.yml
```

### Create environment from file

```bash
conda env create -f environment.yml
fastapi dev main.py
```