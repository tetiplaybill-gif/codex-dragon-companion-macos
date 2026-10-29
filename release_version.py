"""Project release numbering: carry both patch and minor after nine."""
import re

def next_version(current):
    if not re.fullmatch(r'\d+\.\d+\.\d+',current):raise ValueError('Expected major.minor.patch')
    major,minor,patch=map(int,current.split('.'))
    major,minor=major+minor//10,minor%10  # Normalize old intermediate versions.
    if patch>=9:minor+=1;patch=0
    else:patch+=1
    major,minor=major+minor//10,minor%10
    return f'{major}.{minor}.{patch}'

def validate_new_version(version):
    if not re.fullmatch(r'\d+\.[0-9]\.[0-9]',version):raise ValueError('New release minor and patch must be 0–9')
    return version


def validate_public_successor(previous_public,candidate):
    """Public tags advance from the last public release, never a local build."""
    validate_new_version(candidate)
    expected=next_version(previous_public)
    if candidate!=expected:
        raise ValueError(f'Previous public release {previous_public} requires {expected}, got {candidate}')
    return candidate

if __name__=='__main__':
    import sys
    print(next_version(sys.argv[1]))
