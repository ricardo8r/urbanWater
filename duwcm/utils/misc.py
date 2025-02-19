from IPython import get_ipython
def is_notebook():
    try:
        return get_ipython().__class__.__name__ == "ZMQInteractiveShell"
    except NameError:
        return False
