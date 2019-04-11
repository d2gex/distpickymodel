import setuptools
import distpickymodel


def get_long_desc():
    with open("README.rst", "r") as fh:
        return fh.read()


setuptools.setup(
    name="distpickymodel",
    version=distpickymodel.__version__,
    author="Dan G",
    author_email="daniel.garcia@d2garcia.com",
    description="A shared Mongoengine-based model library",
    long_description=get_long_desc(),
    url="https://github.com/d2gex/distpickymodel",
    # Exclude 'tests' and 'docs'
    packages=['distpickymodel'],
    python_requires='>=3.6',
    install_requires=['pymongo>=3.7.2', 'mongoengine>=0.17.0', 'six'],
    tests_require=['pytest>=4.4.0', 'PyYAML>=5.1'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
