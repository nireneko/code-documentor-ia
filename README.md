# POC
Don't use this in production, this project is used to learn langgraph and FastApi.

```bash
conda create -n fastapi python=3.11
conda activate fastapi
conda env export > environment.yml
```

### Create environment from file

```bash
conda env create -f environment.yml
fastapi dev app/analyze.py
```