from setuptools import setup

setup(
    name='stream-compiler',
    packages=['streamcompiler'],
    version='0.1.0',
    description='A video editor based on a human writeable script language',
    author='David Keijser',
    author_email='keijser@gmail.com',
    url='https://github.com/keis/stream-compiler',
    license='ISC',
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'streamc = streamcompiler.__main__:main'
        ]
    },
    python_requires=">=3.6",
    install_requires=[
        'py-scfg',
        'PyGObject'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Multimedia :: Video'
    ],
)
