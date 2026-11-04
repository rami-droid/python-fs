import sys

# file system parameters
TOTAL_SIZE = 0x800 # 2kB

# Metainfo block
HEADER_START = 0x0
# 1 byte counter for the number of files
COUNTER_BYTES = 0x1
# size of file info entry (filename, ...)
FILE_ENTRY_SIZE = 0x10
# size of the file size field in each entry
FILESIZE_SIZE = 0x2
# size of a file block (content of a file)
FILE_BLOCK_SIZE = 0x100
# max number of files (first block is reserved for metainfo, rest are files)
MAX_FILES = (TOTAL_SIZE - FILE_BLOCK_SIZE) // FILE_BLOCK_SIZE


MAX_HARD_LINK_FILES = 0 #TODO: Task 4

# size of block ID field 
BLOCK_ID_SIZE = 0x1
FILENAME_SIZE = FILE_ENTRY_SIZE - FILESIZE_SIZE - BLOCK_ID_SIZE


###### EXCEPTIONS ######
class NoFile(Exception):
    def __init__(self, message="No such file found"):
        self.message = message
        super().__init__(self.message)

class NoFreeSpace(Exception):
    def __init__(self, message="No free space available"):
        self.message = message
        super().__init__(self.message)
        
class EmptyFile(Exception):
    def __init__(self, message="Not allowed to store an empty file"):
        self.message = message
        super().__init__(self.message)


###### FILE SYSTEM OPERATIONS ######

def format(f):
    """
    Formats the file system by writing the initial metadata.
    """
    f.write(b'\0' * TOTAL_SIZE)


def _get_num_files(f):
    f.seek(HEADER_START)
    bytes = f.read(COUNTER_BYTES)
    num = int.from_bytes(bytes, "little", signed=False)
    return num


def _set_num_files(f, n):
    f.seek(HEADER_START)
    bytes = n.to_bytes(COUNTER_BYTES, "little", signed=False)
    f.write(bytes)


def _get_num_linked_files(f):
    pass # Task 4


def _set_num_linked_files(f, n):
    pass # Task 4

   

def save(f, filename, content):
    """
    Saves a file with the given content to the file system.
    
    Args:
        f (file object): The file object representing the file system.
        filename (str): The name of the file to be saved.
        content (str): The file content to be saved.
    """

    num_existing = _get_num_files(f)
    if num_existing >= MAX_FILES:
        raise NoFreeSpace(f"No free space available, max files: {MAX_FILES}")

    new_fileno = None
    for fileno in range(1, MAX_FILES + 1):
        f.seek(HEADER_START + FILE_ENTRY_SIZE * fileno)
        if f.read(FILE_ENTRY_SIZE) == b'\0' * FILE_ENTRY_SIZE:
            new_fileno = fileno
            break

    if new_fileno is None:
        raise NoFreeSpace(f"No free space available, max files: {MAX_FILES}")

    content_bytes = content.encode('ascii')[:FILE_BLOCK_SIZE]
    used_block_ids = set()
    for fileno in range(1, MAX_FILES + 1):
        f.seek(HEADER_START + FILE_ENTRY_SIZE * fileno)
        entry = f.read(FILE_ENTRY_SIZE)
        if entry != b'\0' * FILE_ENTRY_SIZE:
            block_id = int.from_bytes(entry[-BLOCK_ID_SIZE:], 'little')
            if block_id:
                used_block_ids.add(block_id)

    new_block_id = next(
        (block_id for block_id in range(1, MAX_FILES + 1) if block_id not in used_block_ids),
        None,
    )
    if new_block_id is None:
        raise NoFreeSpace(f"No free data blocks, max blocks: {MAX_FILES}")

    entry_start = HEADER_START + FILE_ENTRY_SIZE * new_fileno
    f.seek(entry_start)
    f.write(filename.encode('ascii')[:FILENAME_SIZE].ljust(FILENAME_SIZE, b'\0'))
    f.write(len(content_bytes).to_bytes(FILESIZE_SIZE, 'little'))
    f.write(new_block_id.to_bytes(BLOCK_ID_SIZE, 'little'))
    
    # write content to file block, truncate if needed
    f.seek(HEADER_START + FILE_BLOCK_SIZE * new_block_id)
    f.write(content_bytes)
    _set_num_files(f, num_existing + 1)



def find_fileno(f, filename):
    """
    
    Finds the line of the filename in the header.
    Uses 0-indexing.

    Args:
        f (file object): File system
        filename (str): Name of file

    Returns:
        int: 0-indexed position number
    """
    target_name = filename.encode("ascii")[:FILENAME_SIZE].rstrip(b'\0')
    for pos in range(0, MAX_FILES):
        f.seek(HEADER_START + FILE_ENTRY_SIZE * (pos+1))
        name = f.read(FILENAME_SIZE).rstrip(b'\0')
        if name and name == target_name:
            return pos
    else:
        raise NoFile(f"File {filename} not found")
    
def find_filesize(f, fileno):
    """
    Return the file size of the file associated with
    the given file number.

    Args:
        f (file object): The file system
        fileno (int): The file number
    """
    f.seek(HEADER_START + FILE_ENTRY_SIZE * (fileno + 1) + FILENAME_SIZE)
    filesize = f.read(FILESIZE_SIZE)
    return int.from_bytes(filesize, 'little', signed=False)


def find_block_id(f, fileno):
    f.seek(
        HEADER_START
        + FILE_ENTRY_SIZE * (fileno + 1)
        + FILENAME_SIZE
        + FILESIZE_SIZE
    )
    block_id = f.read(BLOCK_ID_SIZE)
    return int.from_bytes(block_id, 'little', signed=False)


def load(f, filename):
    """
    Load the content of a file from a custom filesystem.
    Args:
        f (file object): The file object representing the file system.
        filename (str): The name of the file to load.
    Returns:
        str: The content of the file as a string.
    """
    
    fileno = find_fileno(f, filename)
    filesize = find_filesize(f, fileno)
    block_id = find_block_id(f, fileno)
    f.seek(HEADER_START + FILE_BLOCK_SIZE * block_id)
    content = f.read(filesize)
    content = content.decode("ascii")
    
    return content

def copy(f, infile, outfile):
    """
    Copy the contents of a file from the filesystem 
    to another file in the filesystem.
    
    Args:
        f (file object): The file object representing the file system.
        infile (str): The name of the file to copy from.
        outfile (str): The name of the new file to copy to.
    """
    content = load(f, infile)
    save(f, outfile, content)


def remove(f, filename):
    """
    Remove a file from the filesystem.
    
    Args:
        f (file object): The file object representing the file system.
        filename (str): The name of the file to remove.
    """
    
    fileno = find_fileno(f, filename)

    f.seek(HEADER_START + FILE_ENTRY_SIZE * (fileno+1))
    f.write(b'\0' * FILE_ENTRY_SIZE)
    
    # update number of files
    num_existing = _get_num_files(f)
    _set_num_files(f, num_existing - 1)
    


def hard_link(f, existing_file, link_name):
    """
    Create a hard link to an existing file.

    Args:
        f (file object): The file object representing the file system.
        existing_file (str): The name of the existing file.
        link_name (str): The name of the new hard link.
    """

    existing_fileno = find_fileno(f, existing_file)
    filesize = find_filesize(f, existing_fileno)
    block_id = find_block_id(f, existing_fileno)

    new_fileno = None
    for fileno in range(1, MAX_FILES + 1):
        f.seek(HEADER_START + FILE_ENTRY_SIZE * fileno)
        if f.read(FILE_ENTRY_SIZE) == b'\0' * FILE_ENTRY_SIZE:
            new_fileno = fileno
            break

    if new_fileno is None:
        raise NoFreeSpace(f"No free space available, max files: {MAX_FILES}")

    entry_start = HEADER_START + FILE_ENTRY_SIZE * new_fileno
    f.seek(entry_start)
    f.write(link_name.encode('ascii')[:FILENAME_SIZE].ljust(FILENAME_SIZE, b'\0'))
    f.write(filesize.to_bytes(FILESIZE_SIZE, 'little'))
    f.write(block_id.to_bytes(BLOCK_ID_SIZE, 'little'))

    _set_num_files(f, _get_num_files(f) + 1)
