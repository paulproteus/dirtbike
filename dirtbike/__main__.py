import sys
from . import make_wheel_file

def main():
    make_wheel_file(sys.argv[1])


if __name__ == '__main__':
    main()
