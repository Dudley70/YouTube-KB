from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="youtube-processor",
    version="0.1.0",
    author="YouTube Processor Team",
    author_email="dev@youtube-processor.com",
    description="Professional CLI tool for YouTube channel processing and video extraction",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "questionary>=2.0",
        "google-api-python-client>=2.0",
        "youtube-transcript-api>=0.6",
        "yt-dlp>=2023.0",
        "requests[socks]>=2.31",
        "PySocks>=1.7"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pytest-mock>=3.0",
            "black>=23.0",
            "isort>=5.0",
            "mypy>=1.0",
            "flake8>=6.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "youtube-processor=youtube_processor.cli:main"
        ]
    },
    include_package_data=True,
    package_data={
        "youtube_processor": ["templates/*.md"]
    }
)