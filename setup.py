from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ragcli",
    version="1.0.0",
    author="ragcli Developers",
    author_email="dev@example.com",
    description="RAG CLI and Web UI for Oracle DB 26ai",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/user/ragcli",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "typer>=0.9.0",
        "click>=8.1.0",
        "rich>=13.7.0",
        "gradio>=4.0.0",
        "oracledb>=1.4.0",
        "pyyaml>=6.0.1",
        "aiohttp>=3.9.0",
        "requests>=2.31.0",
        "plotly>=5.17.0",
        "matplotlib>=3.8.0",
        "langchain-community>=0.0.20",
        "pypdf2>=3.0.1",
        "pdfplumber>=0.10.3",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.0.0",
            "isort>=5.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ragcli=ragcli.cli.main:main",
        ],
    },
)
