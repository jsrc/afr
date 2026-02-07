from setuptools import find_packages, setup

setup(
    name="afr-pusher",
    version="0.1.0",
    description="Fetch AFR news, translate to English, and deliver to WeChat channels",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "requests>=2.32.0",
        "beautifulsoup4>=4.12.0",
    ],
    extras_require={
        "dev": ["pytest>=8.2.0"],
    },
    entry_points={
        "console_scripts": [
            "afr-pusher=afr_pusher.cli:main",
        ]
    },
)
