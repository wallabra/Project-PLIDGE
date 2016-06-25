import struct


class BinaryFileException(BaseException):
    pass


class UnpackingIndexError(BinaryFileException):
    pass


class BinaryFile(object):
    """Helps reading and writing in binary to a file."""

    def __init__(self, filename, initial_position=0, truncate=False):
        # type: (str, int) -> None

        """Provide the data you'll unpack into values and the initial position if it should be bigger than zero."""
        self.position = initial_position
        self.filename = filename
        self.file = open(filename, "ab+")

        if truncate:
            self.file.truncate()

    def set_position(self, byte_position):
        """Sets the header position for read/write operations."""
        self.position = byte_position

    def offset_position(self, byte_offset):
        """Offsets the header position for read/write operations."""
        self.position += byte_offset

    def write_binary_string(self, write_in_position, string, encoding="utf-8"):
        """Writes a string in a Pascal-similiar binary format;
        instead of a byte, a int is used for the string lenght specifier.

        Keeps a pair of the packed bytestring resulted from packing both the string lenght and the string itself."""

        return tuple([self.write_binary(write_in_position, "I", len(string)),
                      self.write_binary(write_in_position, str(len(string)) + "s", string.encode(encoding))])

    def read_binary_string(self):
        """Reads a string in a Pascal-similiar binary format;
        instead of a byte, a int is used for the string lenght specifier."""
        string_size = self.read_binary("I")[0]
        return self.read_binary(str(string_size) + "s")[0]

    def reset_position(self):
        """Sets position back to the start of the file."""
        self.position = 0

    def set_position_to_end(self):
        """Sets position in the end of the file. If the file is changed between a call to this and a call to a IO
        operation function, then the "end" may vary."""
        self.position = len(self.file.read())

    def write_binary(self, write_in_position, byte_format, *data_to_write):
        """Writes some items in binary in the file specified. Similiar to the struct.pack() method,
        but writes directly to the file. Returns the packed written data."""
        write = struct.pack(byte_format, *data_to_write)

        print "Writing {} bytes: \'{}\'".format(len(write), write)

        if write_in_position:
            self.file.seek(self.position)

        else:
            self.file.seek(0, 2)

        self.file.write(write)

        return write

    def read_binary(self, byte_format):
        """Reads and unpacks binary data from the file in the current position."""
        self.file = open(self.filename, "ab+")

        data = self.file.read()

        try:
            if self.position + struct.calcsize(byte_format) > len(data):
                print self.position
                print len(data)
                raise UnpackingIndexError(
                    "The file's content isn't big enough for this unpacking operation at the current position!")

        except struct.error:
            print byte_format
            raise

        print "Reading from format \'{}\' {} bytes at position {}: \'{}\'".format(
            byte_format,
            struct.calcsize(byte_format),
            self.position,
            data[self.position: self.position + struct.calcsize(byte_format)]
        )

        unpacked = struct.unpack(byte_format, data[self.position: self.position + struct.calcsize(byte_format)])
        self.position += struct.calcsize(byte_format)

        print "Result: {}".format(unpacked)
        return unpacked

    def read_binary_named(self, byte_format, *names):
        """Similiar to read_binary, but assigns a name to each value in the tuple.
        Useful for keeping track of the meaning of the unpacked values"""
        data = self.read_binary(byte_format)
        return {names[item]: data[index] for index, item in enumerate(data)}
