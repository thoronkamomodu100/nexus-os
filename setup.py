"""NEXUS OS v3.0 — Setup Configuration"""
from setuptools import setup, find_packages

setup(
    name="nexus-os",
    version="3.0.0",
    description="NEXUS OS — Autonomous AI Operating System",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="NEXUS OS Contributors",
    author_email="",
    url="https://github.com/nexus-os/nexus",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests/*"]),
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "flask>=2.3.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
    },
    entry_points={
        "console_scripts": [
            "nexus=NEXUS_OS_v3:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Artificial Intelligence",
    ],
    keywords="ai autonomous self-improving hyperagents agent evolution",
)
