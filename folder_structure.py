import os  
from pathlib import Path 
import logging 

logging.basicConfig(level=logging.INFO,format='[%(asctime)s]: %(message)s:')

project_name = "Logistic Project" 

list_of_files = [
    ".github/workflows/.gitkeep",
    f"src/{project_name}/__init__.py",
    f"src/{project_name}/components/__init__.py",
    f"src/{project_name}/utils/__init__.py",
    f"src/{project_name}/config/__init__.py",
    f"src/{project_name}/config/configuration.py",
    f"src/{project_name}/pipeline/__init__.py",
    f"src/{project_name}/entity/__init__.py",
    f"src/{project_name}/constants/__init__.py",

    "config/config.yaml",
    "dvc.yaml",
    "params.yaml",
    "requirements.txt",
    "setup.py",
    ".gitignore",
    "README.md",

    "app/main.py",
    "app/config.py",
    "app/database.py",

    "research/trials.ipynb",

    "templates/index.html",

    "static/css/style.css",
    "static/js/script.js",

    "routers/orders.py",
    "routers/warehouse.py",
    "routers/dispatch.py",
    "routers/tracking.py",
    "routers/auth.py",

    "models/order_model.py",
    "models/user_model.py",
    "models/tracking_model.py"
]




for filepath in list_of_files:
    filepath = Path(filepath)
    filedir, filename = os.path.split(filepath)


    if filedir !="":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory; {filedir} for the file: {filename}")

    if (not os.path.exists(filepath)) or (os.path.getsize(filepath) == 0):
        with open(filepath, "w") as f:
            pass
            logging.info(f"Creating empty file: {filepath}")


    else:
        logging.info(f"{filename} is already exists") 