import io

from setuptools import setup, find_packages

with io.open("README.md", "rt", encoding="utf8") as readme_file:
    readme = readme_file.read()

with io.open("VERSION") as version_file:
    version = version_file.read().strip().lower()
    if version.startswith("v"):
        version = version[1:]

setup(
    name="graphql_mcp",
    version=version,
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    author="Robert Parker",
    author_email="rob@parob.com",
    url="https://gitlab.com/parob/graphql-mcp",
    download_url=f"https://gitlab.com/parob/graphql-mcp/-/archive/v{version}"
    f"/graphql_mcp-v{version}.tar.gz",
    keywords=["GraphQL", "GraphQL-API", "GraphQLAPI", "Server", "MCP", "Multi-Model-Protocol"],
    description="A framework for building Python GraphQL MCP servers.",
    long_description=readme,
    long_description_content_type="text/markdown",
    install_requires=[
        "graphql-core~=3.2",
        "fastmcp>=2.11.2",
        "graphql-api>=1.4.13",
        "graphql-http-server>=1.5.7",
        "aiohttp>=3.8.0"
    ],
    extras_require={
        "dev": [
            "graphql-api>=1.4.13",
            "pytest~=5.4",
            "pytest-cov~=2.10",
            "strawberry-graphql~=0.278",
            "coverage~=5.2",
            "faker~=4.1",
            "fastmcp>=2.11.2",
            "pytest-asyncio~=0.18",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
