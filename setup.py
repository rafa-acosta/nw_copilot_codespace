#!/usr/bin/env python
"""Setup script for RAG Data Ingestion Library."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rag-data-ingestion",
    version="1.0.0",
    author="RAG Development Team",
    description="Modular library for ingesting diverse data formats for RAG systems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/rag-data-ingestion",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing",
        "Topic :: Internet",
    ],
    python_requires=">=3.8",
    install_requires=[
        "chromadb>=1.0,<2.0",
        "ragas>=0.4,<0.5",
        "openai>=1.0,<2.0",
        "PyPDF2==3.0.1",
        "beautifulsoup4==4.12.2",
        "requests>=2.32.2,<3.0",
        "python-docx==0.8.11",
        "openpyxl==3.1.5",
        "lxml==4.9.3",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
    },
    keywords="RAG retrieval-augmented generation data ingestion text processing",
)
