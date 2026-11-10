from setuptools import setup, find_packages

setup(
    name="promptgreen",
    version="1.0.0",
    description="Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment",
    author="PromptGreen R&D Group",
    packages=find_packages(),
    install_requires=[
        "click",
        "rich",
        "tiktoken",
        "scikit-learn",
        "numpy",
        "pandas",
        "requests",
        "fastapi",
        "uvicorn",
        "streamlit",
        "plotly",
        "pytest"
    ],
    entry_points={
        "console_scripts": [
            "promptgreen=promptgreen.cli:main",
        ],
    },
)
