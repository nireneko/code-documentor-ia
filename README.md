# POC
Don't use this in production.

```bash
conda create -n fastapi python=3.11
conda activate fastapi
conda install -c conda-forge poetry
conda env export > environment.yml
```

### Create environment from file

```bash
conda env create -f environment.yml
fastapi dev app/analyze.py
```