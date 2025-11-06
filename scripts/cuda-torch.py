"""File: cuda-torch.py
Purpose: capture `nvcc --version` output and print a matching PyTorch pip install command
(optionally run it). Supports replacing the pip command (e.g. use "uv pip")
Usage:
  python cuda-torch.py            print suggested install commands
  python cuda-torch.py --install  interactively run the install
Notes:
  - To use an alternative pip front-end (for example "uv pip"), set environment variable:
      export PIP_CMD='uv pip'
    Default is: python3 -m pip
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys

PIP_CMD_DEFAULT = 'python3 -m pip'


def run_nvcc(nvcc_cmd: str) -> tuple[str | None, str | None]:
    """Return (stdout+stderr, error_message). If nvcc not found, return (None, msg)."""
    if shutil.which(nvcc_cmd) is None:
        return None, f'Error: {nvcc_cmd} not found. Ensure CUDA is installed and nvcc is on PATH.'
    try:
        completed = subprocess.run([nvcc_cmd, '--version'], capture_output=True, text=True, check=False)
        out = completed.stdout + completed.stderr
        return out, None
    except FileNotFoundError:
        return None, f'Error: {nvcc_cmd} not found. Ensure CUDA is installed and nvcc is on PATH.'
    except Exception as e:
        return None, f'Error running {nvcc_cmd}: {e}'


def parse_cuda_version(nvcc_out: str) -> str | None:
    """Parse a CUDA version string like 'release X.Y' or 'Vx.y.z' and return 'X.Y' or None."""
    m = re.search(r'release\s*([0-9]+\.[0-9]+)', nvcc_out, re.IGNORECASE)
    if not m:
        m = re.search(r'V([0-9]+\.[0-9]+)', nvcc_out, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def index_slug_from_cuda(cuda_ver: str | None) -> str:
    if not cuda_ver:
        return 'cpu'
    major, _, minor = cuda_ver.partition('.')
    minor_nozero = minor.lstrip('0')
    if minor_nozero == '':
        tag = major
    else:
        tag = f'{major}{minor_nozero}'
    return f'cu{tag}'


def run_pip_cmd(pip_cmd_arr: list[str], args: list[str]) -> int:
    cmd = pip_cmd_arr + args
    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    except FileNotFoundError:
        print(f'Error: command not found: {pip_cmd_arr[0]}')
        return 2
    except Exception as e:
        print(f'Error running {" ".join(cmd)}: {e}')
        return 3


def main(argv: list[str]) -> int:
    nvcc_cmd = os.environ.get('NVCC_CMD', 'nvcc')
    pip_cmd = os.environ.get('PIP_CMD', PIP_CMD_DEFAULT)
    # split preserving quoting
    pip_cmd_arr = shlex.split(pip_cmd)

    nvcc_out, nvcc_err = run_nvcc(nvcc_cmd)
    if nvcc_err:
        print(nvcc_err)
        # fall back to CPU
        nvcc_out = ''
        cuda_ver = None
    else:
        cuda_ver = parse_cuda_version(nvcc_out or '')

    index_slug = index_slug_from_cuda(cuda_ver)

    packages = 'torch torchvision torchaudio'
    if index_slug == 'cpu':
        index_url = 'https://download.pytorch.org/whl/cpu'
    else:
        index_url = f'https://download.pytorch.org/whl/{index_slug}'

    print('Detected nvcc output (top lines):')
    if nvcc_out:
        for i, line in enumerate((nvcc_out.rstrip('\n').splitlines()), start=1):
            if i > 6:
                break
            print(line)
    else:
        print('<no nvcc output>')

    if cuda_ver:
        print(f'Parsed CUDA version: {cuda_ver} -> PyTorch index: {index_slug}')
    else:
        print('No CUDA version parsed; using CPU index')

    print()
    print(f'Suggested install commands (pip front-end: "{pip_cmd}"):')
    print(f'  {pip_cmd} install --upgrade pip')
    print(f'  {pip_cmd} install {packages} --index-url {index_url}')
    print()

    if len(argv) > 1 and argv[1] == '--install':
        try:
            yn = input('Proceed to run the install commands? (y/N) ').strip()
        except (KeyboardInterrupt, EOFError):
            print('\nInstall cancelled.')
            return 1
        if yn.lower().startswith('y'):
            print(f'Upgrading pip using: {pip_cmd} install --upgrade pip')
            rc = run_pip_cmd(pip_cmd_arr, ['install', '--upgrade', 'pip'])
            if rc != 0:
                print(f'pip upgrade command exited with code {rc}')
                return rc

            print(f'Installing {packages} using: {pip_cmd} install {packages} --index-url {index_url}')
            args = ['install', *packages.split(), '--index-url', index_url]
            rc = run_pip_cmd(pip_cmd_arr, args)
            if rc != 0:
                print(f'install command exited with code {rc}')
                return rc

            print('Done.')
        else:
            print('Install cancelled.')

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
