from setuptools import setup, find_packages

setup(
    name="docsync",
    version="1.0.0",
    description="Automated GitHub Markdown → Confluence documentation sync",
    author="Capstone Team",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "click>=8.1",
        "python-dotenv>=1.0",
        "httpx>=0.27",
        "markdown2>=2.4",
        "pydantic>=2.6",
        "PyYAML>=6.0",
        "structlog>=24.1",
        "tenacity>=8.2",
        "lxml>=5.2",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-asyncio>=0.23",
            "pytest-httpx>=0.30",
            "respx>=0.21",
            "coverage[toml]>=7.4",
        ]
    },
    entry_points={
        "console_scripts": [
            "docsync=docsync.main:main",
        ]
    },
)
