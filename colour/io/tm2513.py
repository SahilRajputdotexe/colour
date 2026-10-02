"""
IES TM-25-13 Ray File Spectral Data Input
=========================================

Define input functionality for the spectral tables stored in *IES TM-25-13*
ray files.

A *IES TM-25-13* ray file starts with a 256 bytes header, followed by a 32
bytes flags block, nine 4000 bytes description fields and the spectral tables
block. The spectral tables are stored back to back, and the block is padded
once, after the last table, so that its total size is a multiple of 32 bytes.
Only these front sections are parsed, the ray data, the column names and the
additional text blocks that follow the spectral tables are ignored.

-   :class:`colour.Header_IESTM2513`
-   :class:`colour.Flags_IESTM2513`
-   :class:`colour.SpectralDistribution_IESTM2513`
-   :func:`colour.read_spectral_distributions_TM2513`

References
----------
-   :cite:`IESComputerCommittee2013` : IES Computer Committee, & TM-25-13
    Working Group. (2013). Ray File Format for the Description of the Emission
    Property of Light Sources. Illuminating Engineering Society.
"""

from __future__ import annotations

import struct
import typing
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from colour.colorimetry import SpectralDistribution

if typing.TYPE_CHECKING:
    from colour.hints import Any, Dict, NDArrayFloat, PathLike, Tuple

__author__ = "Colour Developers"
__copyright__ = "Copyright 2013 Colour Developers"
__license__ = "BSD-3-Clause - https://opensource.org/licenses/BSD-3-Clause"
__maintainer__ = "Colour Developers"
__email__ = "colour-developers@colour-science.org"
__status__ = "Production"

__all__ = [
    "SIGNATURE_IESTM2513",
    "VERSION_IESTM2513",
    "SIZE_HEADER_IESTM2513",
    "SIZE_FLAGS_IESTM2513",
    "SIZE_DESCRIPTION_FIELD_IESTM2513",
    "DESCRIPTION_FIELDS_IESTM2513",
    "SPECTRAL_TABLE_ALIGNMENT_IESTM2513",
    "IESTM2513Error",
    "Flags_IESTM2513",
    "Header_IESTM2513",
    "SpectralDistribution_IESTM2513",
    "read_spectral_distributions_TM2513",
]

SIGNATURE_IESTM2513: bytes = b"TM25"
"""*IES TM-25-13* ray file signature."""

VERSION_IESTM2513: int = 2013
"""*IES TM-25-13* ray file version."""

SIZE_HEADER_IESTM2513: int = 256
"""*IES TM-25-13* header size in bytes."""

SIZE_FLAGS_IESTM2513: int = 32
"""*IES TM-25-13* flags block size in bytes."""

SIZE_DESCRIPTION_FIELD_IESTM2513: int = 4000
"""*IES TM-25-13* description field size in bytes."""

DESCRIPTION_FIELDS_IESTM2513: tuple[str, ...] = (
    "name",
    "manufacturer",
    "model_creator",
    "rayfile_creator",
    "equipment",
    "camera",
    "lightsource",
    "additional_info",
    "data_reference",
)
"""*IES TM-25-13* description field names, in file order."""

SPECTRAL_TABLE_ALIGNMENT_IESTM2513: int = 32
"""
*IES TM-25-13* alignment in bytes of the size of the spectral tables block,
which is padded once, after the last spectral table.
"""

_STRUCT_HEADER_IESTM2513: struct.Struct = struct.Struct("<4s ii ff Q 28s i i fff iii")
_SIZE_RESERVED_IESTM2513: int = SIZE_HEADER_IESTM2513 - _STRUCT_HEADER_IESTM2513.size


class IESTM2513Error(ValueError):
    """
    Define the exception raised when an *IES TM-25-13* ray file or one of its
    sections is malformed.
    """


@dataclass
class Flags_IESTM2513:
    """
    Define the *IES TM-25-13* known data flags block, section 4.7.2.

    Parameters
    ----------
    position
        Whether the ray positions are defined, the standard requires it.
    direction
        Whether the ray directions are defined, the standard requires it.
    rad_flux
        Whether the ray radiant flux, i.e. the Stokes parameter S0, is
        defined.
    lambda_flag
        Whether the ray wavelengths are defined.
    lum_flux
        Whether the ray luminous flux, i.e. the tristimulus value Y, is
        defined.
    stokes
        Whether the ray Stokes parameters are defined.
    tristimulus
        Whether the ray tristimulus values are defined.
    spectrum_index
        Whether the rays carry a spectral table index.

    Examples
    --------
    >>> import struct
    >>> data = struct.pack("<8i", 1, 1, 1, 0, 0, 0, 0, 1)
    >>> flags = Flags_IESTM2513.from_bytes(data)
    >>> flags.rad_flux, flags.lambda_flag, flags.spectrum_index
    (True, False, True)
    """

    position: bool = True
    direction: bool = True
    rad_flux: bool = False
    lambda_flag: bool = False
    lum_flux: bool = False
    stokes: bool = False
    tristimulus: bool = False
    spectrum_index: bool = False

    @classmethod
    def from_bytes(cls, data: bytes) -> Flags_IESTM2513:
        """
        Parse the specified flags block.

        Parameters
        ----------
        data
            Flags block, made of 8 little-endian *int32* values.

        Returns
        -------
        :class:`colour.Flags_IESTM2513`
            Parsed flags.

        Raises
        ------
        :class:`colour.IESTM2513Error`
            If the block does not have the expected size or if a flag is
            neither 0 nor 1.

        Examples
        --------
        >>> import struct
        >>> data = struct.pack("<8i", 1, 1, 0, 1, 0, 0, 0, 0)
        >>> Flags_IESTM2513.from_bytes(data).lambda_flag
        True
        """

        if len(data) != SIZE_FLAGS_IESTM2513:
            message = (
                f"Flags block must be {SIZE_FLAGS_IESTM2513} bytes, got {len(data)}!"
            )
            raise IESTM2513Error(message)

        values = struct.unpack("<8i", data)
        for index, value in enumerate(values):
            if value not in (0, 1):
                message = f"Flag {index} must be 0 or 1, got {value}!"
                raise IESTM2513Error(message)

        return cls(*(bool(value) for value in values))

    def as_tuple(self) -> Tuple[bool, ...]:
        """
        Return the flags as a tuple, in file order.

        Returns
        -------
        :class:`tuple`
            Flags.

        Examples
        --------
        >>> Flags_IESTM2513(rad_flux=True, spectrum_index=True).as_tuple()
        (True, True, True, False, False, False, False, True)
        """

        return (
            self.position,
            self.direction,
            self.rad_flux,
            self.lambda_flag,
            self.lum_flux,
            self.stokes,
            self.tristimulus,
            self.spectrum_index,
        )


@dataclass
class Header_IESTM2513:
    """
    Define the *IES TM-25-13* ray file header, section 4.7.1.

    Parameters
    ----------
    file_type
        File signature, 4 ASCII bytes.
    version
        File format version.
    creation_method
        Method used to create the file.
    phi_v
        Total luminous flux of the source.
    phi
        Total radiant flux of the source.
    n_rays
        Number of rays.
    file_date_time
        File creation date and time, as an ASCII string.
    start_position
        Ray start position code.
    spectrum_type
        Spectral data identifier, from 0 to 4: 0 for no spectral data, 1 for a
        single wavelength, 2 for a wavelength per ray, 3 for spectral tables
        that apply to all the rays and 4 for a spectral table index per ray.
    lambda_
        Single wavelength, used when the spectral data identifier is 1.
    lambda_min
        Minimum wavelength.
    lambda_max
        Maximum wavelength.
    n_spectra
        Number of spectral tables.
    n_addtl_items
        Number of additional items per ray.
    text_block_size
        Size in bytes of the trailing additional text block.
    reserved
        Reserved bytes.

    Examples
    --------
    >>> Header_IESTM2513(n_spectra=2).n_spectra
    2
    """

    file_type: bytes = SIGNATURE_IESTM2513
    version: int = VERSION_IESTM2513
    creation_method: int = 0
    phi_v: float = 0.0
    phi: float = 0.0
    n_rays: int = 0
    file_date_time: str = ""
    start_position: int = 0
    spectrum_type: int = 0
    lambda_: float = 0.0
    lambda_min: float = 0.0
    lambda_max: float = 0.0
    n_spectra: int = 0
    n_addtl_items: int = 0
    text_block_size: int = 0
    reserved: bytes = field(default_factory=lambda: bytes(_SIZE_RESERVED_IESTM2513))

    @classmethod
    def from_bytes(cls, data: bytes) -> Header_IESTM2513:
        """
        Parse the specified header block.

        Parameters
        ----------
        data
            Header block, made of 256 bytes with little-endian integers and
            floats.

        Returns
        -------
        :class:`colour.Header_IESTM2513`
            Parsed header.

        Raises
        ------
        :class:`colour.IESTM2513Error`
            If the block does not have the expected size, if the signature is
            not :attr:`colour.io.SIGNATURE_IESTM2513`, if the version is not
            positive, if the spectral data identifier is not between 0 and 4
            or if the number of spectra, additional items or the text block
            size is negative.

        Examples
        --------
        >>> from os.path import dirname, join
        >>> directory = join(dirname(__file__), "tests", "resources")
        >>> with open(join(directory, "TM25_Sample.tm25"), "rb") as ray_file:
        ...     header = Header_IESTM2513.from_bytes(ray_file.read(256))
        >>> header.file_type, header.n_spectra
        (b'TM25', 2)
        """

        if len(data) != SIZE_HEADER_IESTM2513:
            message = f"Header must be {SIZE_HEADER_IESTM2513} bytes, got {len(data)}!"
            raise IESTM2513Error(message)

        if data[:4] != SIGNATURE_IESTM2513:
            message = (
                f"Header signature must be {SIGNATURE_IESTM2513!r}, got {data[:4]!r}!"
            )
            raise IESTM2513Error(message)

        (
            file_type,
            version,
            creation_method,
            phi_v,
            phi,
            n_rays,
            file_date_time,
            start_position,
            spectrum_type,
            lambda_,
            lambda_min,
            lambda_max,
            n_spectra,
            n_addtl_items,
            text_block_size,
        ) = _STRUCT_HEADER_IESTM2513.unpack_from(data)

        if version <= 0:
            message = f'"version" must be positive, got {version}!'
            raise IESTM2513Error(message)

        if not 0 <= spectrum_type <= 4:
            message = f'"spectrum_type" must be between 0 and 4, got {spectrum_type}!'
            raise IESTM2513Error(message)

        for name, value in (
            ("n_spectra", n_spectra),
            ("n_addtl_items", n_addtl_items),
            ("text_block_size", text_block_size),
        ):
            if value < 0:
                message = f'"{name}" must be non-negative, got {value}!'
                raise IESTM2513Error(message)

        return cls(
            file_type=file_type,
            version=version,
            creation_method=creation_method,
            phi_v=phi_v,
            phi=phi,
            n_rays=n_rays,
            file_date_time=file_date_time.split(b"\x00", 1)[0].decode(
                "ascii", errors="replace"
            ),
            start_position=start_position,
            spectrum_type=spectrum_type,
            lambda_=lambda_,
            lambda_min=lambda_min,
            lambda_max=lambda_max,
            n_spectra=n_spectra,
            n_addtl_items=n_addtl_items,
            text_block_size=text_block_size,
            reserved=data[_STRUCT_HEADER_IESTM2513.size :],
        )


def _decode_description_field(data: bytes) -> str:
    """Decode a description field up to its first NUL character."""

    return data.decode("utf-32-le", errors="replace").split("\x00", 1)[0]


def _read_descriptions(blob: bytes, offset: int) -> Tuple[Dict[str, str], int]:
    """
    Read the description fields starting at the specified offset and return
    them along with the offset of the next section.
    """

    size = SIZE_DESCRIPTION_FIELD_IESTM2513
    end = offset + len(DESCRIPTION_FIELDS_IESTM2513) * size
    if end > len(blob):
        message = "File is truncated inside the description fields!"
        raise IESTM2513Error(message)

    descriptions = {
        name: _decode_description_field(blob[start : start + size])
        for name, start in zip(
            DESCRIPTION_FIELDS_IESTM2513, range(offset, end, size), strict=True
        )
    }

    return descriptions, end


def _read_spectral_table(
    blob: bytes, offset: int
) -> Tuple[NDArrayFloat, NDArrayFloat, int]:
    """
    Read the spectral table starting at the specified offset and return its
    wavelengths and weights along with the offset following the table.
    """

    if offset + 4 > len(blob):
        message = "File is truncated before a spectral table pair count!"
        raise IESTM2513Error(message)

    (pair_count,) = struct.unpack_from("<i", blob, offset)
    if pair_count <= 0:
        message = f"Spectral table pair count must be positive, got {pair_count}!"
        raise IESTM2513Error(message)

    end = offset + 4 + pair_count * 8
    if end > len(blob):
        message = "File is truncated inside a spectral table!"
        raise IESTM2513Error(message)

    pairs = np.frombuffer(blob, dtype="<f4", count=pair_count * 2, offset=offset + 4)
    pairs = pairs.reshape(pair_count, 2).astype(np.float64)

    return pairs[:, 0], pairs[:, 1], end


class SpectralDistribution_IESTM2513(SpectralDistribution):
    """
    Define an *IES TM-25-13* spectral distribution, i.e. one spectral table of
    a ray file along with the metadata of the file.

    Parameters
    ----------
    path
        *IES TM-25-13* ray file path.
    header
        Ray file header.
    flags
        Ray file flags.
    descriptions
        Ray file description fields, missing keys of
        :attr:`colour.io.DESCRIPTION_FIELDS_IESTM2513` default to an empty
        string.
    spectrum_index
        Zero-based index of the spectral table in the ray file.

    Other Parameters
    ----------------
    kwargs
        Keyword arguments for the :class:`colour.SpectralDistribution` class.

    Attributes
    ----------
    -   :attr:`~colour.SpectralDistribution_IESTM2513.path`
    -   :attr:`~colour.SpectralDistribution_IESTM2513.header`
    -   :attr:`~colour.SpectralDistribution_IESTM2513.flags`
    -   :attr:`~colour.SpectralDistribution_IESTM2513.descriptions`
    -   :attr:`~colour.SpectralDistribution_IESTM2513.spectrum_index`

    Methods
    -------
    -   :meth:`~colour.SpectralDistribution_IESTM2513.read`

    Examples
    --------
    >>> from os.path import dirname, join
    >>> directory = join(dirname(__file__), "tests", "resources")
    >>> sd = SpectralDistribution_IESTM2513(
    ...     join(directory, "TM25_Sample.tm25"), spectrum_index=1
    ... ).read()
    >>> sd.descriptions["manufacturer"]
    'Sample Manufacturer'
    >>> sd.shape
    SpectralShape(400.0, 700.0, 75.0)
    """

    def __init__(
        self,
        path: str | PathLike | None = None,
        header: Header_IESTM2513 | None = None,
        flags: Flags_IESTM2513 | None = None,
        descriptions: Dict[str, str] | None = None,
        spectrum_index: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._path: str | None = None
        self.path = path
        self._header: Header_IESTM2513 = Header_IESTM2513()
        self.header = header or Header_IESTM2513()
        self._flags: Flags_IESTM2513 = Flags_IESTM2513()
        self.flags = flags or Flags_IESTM2513()
        self._descriptions: Dict[str, str] = {}
        self.descriptions = descriptions or {}
        self._spectrum_index: int = 0
        self.spectrum_index = spectrum_index

    @property
    def path(self) -> str | None:
        """
        Getter and setter for the ray file path.

        Parameters
        ----------
        value
            Value to set the ray file path with.

        Returns
        -------
        :class:`str` or :py:data:`None`
            Ray file path.
        """

        return self._path

    @path.setter
    def path(self, value: str | PathLike | None) -> None:
        """Setter for the **self.path** property."""

        self._path = None if value is None else str(value)

    @property
    def header(self) -> Header_IESTM2513:
        """
        Getter and setter for the ray file header.

        Parameters
        ----------
        value
            Value to set the ray file header with.

        Returns
        -------
        :class:`colour.Header_IESTM2513`
            Ray file header.
        """

        return self._header

    @header.setter
    def header(self, value: Header_IESTM2513) -> None:
        """Setter for the **self.header** property."""

        self._header = value

    @property
    def flags(self) -> Flags_IESTM2513:
        """
        Getter and setter for the ray file flags.

        Parameters
        ----------
        value
            Value to set the ray file flags with.

        Returns
        -------
        :class:`colour.Flags_IESTM2513`
            Ray file flags.
        """

        return self._flags

    @flags.setter
    def flags(self, value: Flags_IESTM2513) -> None:
        """Setter for the **self.flags** property."""

        self._flags = value

    @property
    def descriptions(self) -> Dict[str, str]:
        """
        Getter and setter for the ray file description fields.

        Parameters
        ----------
        value
            Value to set the ray file description fields with, missing keys
            of :attr:`colour.io.DESCRIPTION_FIELDS_IESTM2513` default to an
            empty string and unknown keys are ignored.

        Returns
        -------
        :class:`dict`
            Ray file description fields, with a key for each of
            :attr:`colour.io.DESCRIPTION_FIELDS_IESTM2513`.
        """

        return self._descriptions

    @descriptions.setter
    def descriptions(self, value: Dict[str, str]) -> None:
        """Setter for the **self.descriptions** property."""

        self._descriptions = {
            name: value.get(name, "") for name in DESCRIPTION_FIELDS_IESTM2513
        }

    @property
    def spectrum_index(self) -> int:
        """
        Getter and setter for the spectral table index.

        Parameters
        ----------
        value
            Value to set the zero-based spectral table index with.

        Returns
        -------
        :class:`int`
            Spectral table index.
        """

        return self._spectrum_index

    @spectrum_index.setter
    def spectrum_index(self, value: int) -> None:
        """Setter for the **self.spectrum_index** property."""

        self._spectrum_index = int(value)

    def read(self) -> SpectralDistribution_IESTM2513:
        """
        Read the spectral table selected by the spectrum index from the ray
        file at the specified path.

        Returns
        -------
        :class:`colour.SpectralDistribution_IESTM2513`
            *IES TM-25-13* spectral distribution.

        Raises
        ------
        :class:`colour.IESTM2513Error`
            If the path is undefined, if the file is malformed, if it does not
            contain any spectral table or if the spectral table index is out of
            range.

        Examples
        --------
        >>> from os.path import dirname, join
        >>> directory = join(dirname(__file__), "tests", "resources")
        >>> sd = SpectralDistribution_IESTM2513(join(directory, "TM25_Sample.tm25"))
        >>> sd.read().name
        'Sample Lamp (0)'
        """

        if self._path is None:
            message = "The ray file path is undefined!"
            raise IESTM2513Error(message)

        sds = read_spectral_distributions_TM2513(self._path)
        if not sds:
            message = "The ray file does not contain any spectral table!"
            raise IESTM2513Error(message)

        if not 0 <= self._spectrum_index < len(sds):
            message = (
                f'The spectral table index "{self._spectrum_index}" is out of '
                f'range, the ray file has "{len(sds)}" spectral tables!'
            )
            raise IESTM2513Error(message)

        sd = sds[self._spectrum_index]
        self.name = sd.name
        self.header = sd.header
        self.flags = sd.flags
        self.descriptions = sd.descriptions
        self.wavelengths = sd.wavelengths
        self.values = sd.values

        return self


def read_spectral_distributions_TM2513(
    path: str | PathLike,
) -> list[SpectralDistribution_IESTM2513]:
    """
    Read all the spectral tables of the specified *IES TM-25-13* ray file and
    convert them to :class:`colour.SpectralDistribution_IESTM2513` class
    instances.

    Parameters
    ----------
    path
        *IES TM-25-13* ray file path.

    Returns
    -------
    :class:`list`
        :class:`colour.SpectralDistribution_IESTM2513` class instances, one
        for each spectral table, in file order. The spectral distributions
        share the header, flags and descriptions of the file.

    Raises
    ------
    :class:`colour.IESTM2513Error`
        If the file is malformed or truncated.

    Notes
    -----
    -   The spectral tables are stored back to back and the block they form
        is padded once, after the last table, to a multiple of 32 bytes.
    -   The ray data, the column names and the additional text block that
        follow the spectral tables are not read.
    -   The spectral distributions are named after the "name" description
        field, or the file name if it is empty, followed by the spectral table
        index if the file contains more than one spectral table.

    Examples
    --------
    >>> from os.path import dirname, join
    >>> directory = join(dirname(__file__), "tests", "resources")
    >>> sds = read_spectral_distributions_TM2513(join(directory, "TM25_Sample.tm25"))
    >>> len(sds)
    2
    >>> sds[0].name
    'Sample Lamp (0)'
    >>> sds[1].wavelengths.tolist()
    [400.0, 475.0, 550.0, 625.0, 700.0]
    """

    path = Path(path)
    blob = path.read_bytes()

    if len(blob) < SIZE_HEADER_IESTM2513:
        message = f"File is shorter than the {SIZE_HEADER_IESTM2513} bytes header!"
        raise IESTM2513Error(message)

    header = Header_IESTM2513.from_bytes(blob[:SIZE_HEADER_IESTM2513])

    offset = SIZE_HEADER_IESTM2513 + SIZE_FLAGS_IESTM2513
    if offset > len(blob):
        message = "File is truncated inside the flags block!"
        raise IESTM2513Error(message)

    flags = Flags_IESTM2513.from_bytes(blob[SIZE_HEADER_IESTM2513:offset])
    descriptions, offset = _read_descriptions(blob, offset)

    name = descriptions["name"] or path.name

    start = offset
    tables = []
    for _ in range(header.n_spectra):
        wavelengths, weights, offset = _read_spectral_table(blob, offset)
        tables.append((wavelengths, weights))

    if tables:
        offset += -(offset - start) % SPECTRAL_TABLE_ALIGNMENT_IESTM2513
        if offset > len(blob):
            message = "File is truncated inside the spectral tables padding!"
            raise IESTM2513Error(message)

    sds = []
    for index, (wavelengths, weights) in enumerate(tables):
        sds.append(
            SpectralDistribution_IESTM2513(
                path,
                header,
                flags,
                descriptions,
                index,
                data=weights,
                domain=wavelengths,
                name=f"{name} ({index})" if header.n_spectra > 1 else name,
            )
        )

    return sds
