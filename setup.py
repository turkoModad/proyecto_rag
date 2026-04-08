from setuptools import setup, find_packages

setup(
    name='proyecto_rag',
    version='0.1.0',
    packages=['app', 'compartido', 'email_service'] + find_packages(exclude=['frontend', 'static', 'scripts', 'data', 'models']),
    package_dir={
        'app': 'app',
        'compartido': 'compartido',
        'email_service': 'email_service',
    },
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
    description='Módulos reutilizables para RAG',
    author='CodePyhub',
)
