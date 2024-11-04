Geo IP sets
============
Contributions are welcome. 

Workflow
------------
To do so, please follow the [Git feature branch workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow).

Pre-commit Linting
-------------------
Please setup [flake8 linting as a pre-commit hook](https://flake8.pycqa.org/en/latest/user/using-hooks.html) in your local repo.

The following minimal pre-commit-config.yaml is enough:
```yaml
files: 'python/'
repos:
  - repo: https://github.com/pycqa/flake8
    rev: 7.1.1
    hooks:
      - id: flake8
        args: ['--max-line-length', '120']
```