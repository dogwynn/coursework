import re
from pathlib import Path

from setuptools import setup, find_packages

HERE = Path(__file__).resolve().parent

version_re = re.compile(r"^__version__\s*=\s*'(?P<version>.*)'$", re.M)
def version():
    match = version_re.search(Path('coursework/__init__.py').read_text())
    if match:
        return match.groupdict()['version'].strip()
    return '0.0.1'

long_description = Path(HERE, 'README.md').resolve().read_text()

setup(
    name='coursework',
    packages=find_packages(
        exclude=['config', 'tests'],
    ),
    package_dir={
        'coursework': 'coursework',
    },

    install_requires=[
        'requests',
        'larc',
        'toolz',
        'click',
        'pyrsistent',
    ],

    version=version(),
    description=('Python API for course materials using Canvas LMS'),
    long_description=long_description,

    url='https://github.org/dogwynn/coursework',

    author='Lowland Applied Research Company (LARC)',
    author_email='dogwynn@lowlandresearch.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.7',
    ],

    zip_safe=False,

    keywords=('education utilities canvas canvaslms rest api'),

    scripts=[
    ],

    entry_points={
        'console_scripts': [
            'coursework-init-course=coursework.cli.course:init_course',
            'coursework-sync-modules=coursework.cli.module:sync_modules',
            'coursework-render-slide=coursework.cli.slide:render_slide_html',
            'coursework-sync-slides=coursework.cli.slide:sync_slides',
            'coursework-sync-pages=coursework.cli.page:sync_pages',
            'coursework-sync-quizzes=coursework.cli.quiz:sync_quizzes',
            'coursework-sync-assignments=coursework.cli.assignment:sync_assignments',
        ],
    },
)
