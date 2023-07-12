import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cudawatch",
    version="0.1.0",
    author="Quim Aguado",
    author_email="",
    description="Monitor GPU usage of CUDA programs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/quim0/cudawatch",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    setup_requires=['wheel'],
    entry_points = {
        'console_scripts': ['cudawatch=cudawatch.cudawatch:cudawatch'],
    }
)
