import atexit
from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install


def _post_install():
    """Download Chromium for kaleido static image export."""
    try:
        import kaleido
        kaleido.get_chrome_sync()
        print("✓ Chromium downloaded for kaleido image export.")
    except Exception as e:
        print(f"⚠ Could not download Chromium for kaleido: {e}")
        print("  Run 'python -c \"import kaleido; kaleido.get_chrome_sync()\"' manually.")


class PostInstall(install):
    def run(self):
        install.run(self)
        _post_install()


class PostDevelop(develop):
    def run(self):
        develop.run(self)
        _post_install()


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="urbanWater",
    version="0.1.0",
    author="Ricardo",
    author_email="ricardo.reyes@eawag.ch",
    description="Distributed urban water cycle model",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ricardo8r/urbanWater",
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
    cmdclass={
        "install": PostInstall,
        "develop": PostDevelop,
    },
    entry_points={
        "console_scripts": [
            "duwcm=duwcm.main:main",
            "duwcm-plot=duwcm.plots:plot_all",
            "duwcm-point=duwcm.postprocess:save_cell"
        ],
    },
)
