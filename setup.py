from setuptools import setup, find_packages

setup(
    name='proyecto_rag',
    version='0.1.0',
    packages=find_packages(exclude=['frontend', 'static', 'scripts', 'data', 'models', 'duplicados.csv']),
    install_requires=[
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'pyjwt',
        'python-multipart',
        'python-dotenv',
        'bcrypt',
        'passlib',
        'email-validator',
        'pydantic',
        'pydantic-settings',
    ],
    python_requires='>=3.10, <3.12',
    description='Módulos reutilizables para RAG - Autenticación, Email, Compartición',
    author='CodePyhub',
    author_email='turkomodad88@gmail.com',
    url='https://github.com/turkoModad/proyecto_rag',
    classifiers=[
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)