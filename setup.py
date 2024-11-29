from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="duwcm",
    version="0.1.0",
    author="Ricardo",
    author_email="ricardo.reyes@eawag.ch",
    description="Distributed urban water cycle model",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ricardo8r/duwcm",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "pandas",
        "numpy",
        "simpledbf",
        "matplotlib",
        "dynaconf",
    ],
    entry_points={
        "console_scripts": [
            "duwcm=duwcm.main:main",
            "duwcm-plot=duwcm.plots:plot_all",
            "duwcm-point=duwcm.postprocess:save_cell"
        ],
    },
)
