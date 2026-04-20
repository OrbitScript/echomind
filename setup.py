from setuptools import setup, find_packages
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()
setup(
    name="echomind",
    version="1.0.0",
    description="The AI that argues with itself — multi-persona live terminal debates",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/OrbitScript/echomind",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={"dev": ["pytest>=7.0"]},
    entry_points={"console_scripts": ["echomind=echomind.cli:main"]},
)
