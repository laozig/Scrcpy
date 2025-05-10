from setuptools import setup, find_packages

setup(
    name="ScrcpyGUI",
    version="1.0.0",
    description="GUI界面for scrcpy工具，用于显示和控制Android设备",
    author="Scrcpy GUI Contributors",
    packages=find_packages(),
    py_modules=["main", "scrcpy_controller", "utils"],
    python_requires=">=3.6",
    install_requires=[
        "PyQt5>=5.15.2",
    ],
    entry_points={
        "console_scripts": [
            "scrcpy-gui=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
) 