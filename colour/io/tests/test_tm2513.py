"""Define the unit tests for the :mod:`colour.io.tm2513` module."""

from __future__ import annotations

import os
import struct
import typing
from dataclasses import fields

import numpy as np
import pytest

from colour.io.tm2513 import (
    DESCRIPTION_FIELDS_IESTM2513,
    SIGNATURE_IESTM2513,
    SIZE_DESCRIPTION_FIELD_IESTM2513,
    SIZE_FLAGS_IESTM2513,
    SIZE_HEADER_IESTM2513,
    SPECTRAL_TABLE_ALIGNMENT_IESTM2513,
    VERSION_IESTM2513,
    Flags_IESTM2513,
    Header_IESTM2513,
    IESTM2513Error,
    SpectralDistribution_IESTM2513,
    read_spectral_distributions_TM2513,
)
from colour.utilities import xp_assert_close

if typing.TYPE_CHECKING:
    from pathlib import Path

__author__ = "Colour Developers"
__copyright__ = "Copyright 2013 Colour Developers"
__license__ = "BSD-3-Clause - https://opensource.org/licenses/BSD-3-Clause"
__maintainer__ = "Colour Developers"
__email__ = "colour-developers@colour-science.org"
__status__ = "Production"

__all__ = [
    "ROOT_RESOURCES",
    "TM25_SAMPLE_FILE",
    "TABLE_A",
    "TABLE_B",
    "TABLE_C",
    "build_header",
    "build_flags",
    "build_descriptions",
    "build_spectral_tables",
    "build_file",
    "TestIES_TM2513_Flags",
    "TestIES_TM2513_Header",
    "TestIES_TM2513_Sd",
    "TestReadSpectralDistributionsTM2513",
]

ROOT_RESOURCES: str = os.path.join(os.path.dirname(__file__), "resources")

TM25_SAMPLE_FILE: str = os.path.join(ROOT_RESOURCES, "TM25_Sample.tm25")

TABLE_A: list = [(400.0, 0.125), (500.0, 0.5), (600.0, 0.875), (700.0, 0.25)]
TABLE_B: list = [(450.0, 0.25), (550.0, 0.75), (650.0, 0.5)]
TABLE_C: list = [(420.0, 1.0), (520.0, 0.5)]


def build_header(**kwargs: typing.Any) -> bytes:
    """Build a 256 bytes *IES TM-25-13* header, overridden by `kwargs`."""

    fields = {
        "file_type": SIGNATURE_IESTM2513,
        "version": VERSION_IESTM2513,
        "creation_method": 1,
        "phi_v": 100.0,
        "phi": 350.0,
        "n_rays": 1000,
        "file_date_time": b"2013-06-01T12:30:00",
        "start_position": 0,
        "spectrum_type": 3,
        "lambda_": 0.0,
        "lambda_min": 400.0,
        "lambda_max": 700.0,
        "n_spectra": 1,
        "n_addtl_items": 0,
        "text_block_size": 0,
    }
    fields.update(kwargs)

    data = struct.pack("<4s ii ff Q 28s i i fff iii", *fields.values())

    return data + bytes(SIZE_HEADER_IESTM2513 - len(data))


def build_flags(*values: int) -> bytes:
    """Build a 32 bytes *IES TM-25-13* flags block."""

    return struct.pack("<8i", *(values or (1, 1, 1, 0, 1, 0, 0, 0)))


def build_descriptions(**kwargs: str) -> bytes:
    """Build the nine *IES TM-25-13* description fields."""

    size = SIZE_DESCRIPTION_FIELD_IESTM2513
    fields = []
    for name in DESCRIPTION_FIELDS_IESTM2513:
        data = kwargs.get(name, "").encode("utf-32-le")
        fields.append(data + bytes(size - len(data)))

    return b"".join(fields)


def build_spectral_tables(tables: list) -> bytes:
    """
    Build the *IES TM-25-13* spectral tables block, i.e. the tables back to
    back, padded once to a multiple of 32 bytes.
    """

    data = b""
    for pairs in tables:
        data += struct.pack("<i", len(pairs))
        data += b"".join(struct.pack("<ff", *pair) for pair in pairs)

    if tables:
        data += bytes(-len(data) % SPECTRAL_TABLE_ALIGNMENT_IESTM2513)

    return data


def build_file(tables: list, **kwargs: str) -> bytes:
    """Build an *IES TM-25-13* ray file front section."""

    return (
        build_header(n_spectra=len(tables))
        + build_flags()
        + build_descriptions(**kwargs)
        + build_spectral_tables(tables)
    )


class TestIES_TM2513_Flags:
    """
    Define :class:`colour.io.tm2513.Flags_IESTM2513` class unit tests
    methods.
    """

    def test_required_attributes(self) -> None:
        """Test the presence of required attributes."""

        assert [field.name for field in fields(Flags_IESTM2513)] == [
            "position",
            "direction",
            "rad_flux",
            "lambda_flag",
            "lum_flux",
            "stokes",
            "tristimulus",
            "spectrum_index",
        ]

    def test_required_methods(self) -> None:
        """Test the presence of required methods."""

        required_methods = ("from_bytes", "as_tuple")

        for method in required_methods:
            assert method in dir(Flags_IESTM2513)

    def test_from_bytes(self) -> None:
        """Test :meth:`colour.io.tm2513.Flags_IESTM2513.from_bytes` method."""

        flags = Flags_IESTM2513.from_bytes(build_flags(1, 0, 1, 0, 1, 0, 1, 0))

        assert flags == Flags_IESTM2513(
            position=True,
            direction=False,
            rad_flux=True,
            lambda_flag=False,
            lum_flux=True,
            stokes=False,
            tristimulus=True,
            spectrum_index=False,
        )

        flags = Flags_IESTM2513.from_bytes(build_flags(0, 0, 0, 1, 0, 1, 0, 1))

        assert flags.lambda_flag
        assert flags.stokes
        assert flags.spectrum_index
        assert not flags.rad_flux
        assert not flags.lum_flux
        assert not flags.tristimulus

    def test_raise_exception_from_bytes(self) -> None:
        """
        Test :meth:`colour.io.tm2513.Flags_IESTM2513.from_bytes` method
        raised exception.
        """

        with pytest.raises(IESTM2513Error):
            Flags_IESTM2513.from_bytes(build_flags()[:-4])

        with pytest.raises(IESTM2513Error):
            Flags_IESTM2513.from_bytes(build_flags(1, 1, 0, 0, 0, 0, 2, 0))

        with pytest.raises(IESTM2513Error):
            Flags_IESTM2513.from_bytes(build_flags(1, 1, 0, 0, 0, 0, 0, -1))

    def test_as_tuple(self) -> None:
        """Test :meth:`colour.io.tm2513.Flags_IESTM2513.as_tuple` method."""

        flags = Flags_IESTM2513.from_bytes(build_flags(0, 1, 0, 1, 0, 1, 0, 1))

        assert flags.as_tuple() == (
            False,
            True,
            False,
            True,
            False,
            True,
            False,
            True,
        )


class TestIES_TM2513_Header:
    """
    Define :class:`colour.io.tm2513.Header_IESTM2513` class unit tests
    methods.
    """

    def test_required_attributes(self) -> None:
        """Test the presence of required attributes."""

        assert [field.name for field in fields(Header_IESTM2513)] == [
            "file_type",
            "version",
            "creation_method",
            "phi_v",
            "phi",
            "n_rays",
            "file_date_time",
            "start_position",
            "spectrum_type",
            "lambda_",
            "lambda_min",
            "lambda_max",
            "n_spectra",
            "n_addtl_items",
            "text_block_size",
            "reserved",
        ]

    def test_required_methods(self) -> None:
        """Test the presence of required methods."""

        assert "from_bytes" in dir(Header_IESTM2513)

    def test_from_bytes(self) -> None:
        """Test :meth:`colour.io.tm2513.Header_IESTM2513.from_bytes` method."""

        header = Header_IESTM2513.from_bytes(
            build_header(
                n_rays=2**40,
                phi_v=12.5,
                phi=7.25,
                lambda_=550.0,
                n_spectra=3,
                n_addtl_items=2,
                text_block_size=128,
            )
        )

        assert header == Header_IESTM2513(
            file_type=b"TM25",
            version=2013,
            creation_method=1,
            phi_v=12.5,
            phi=7.25,
            n_rays=2**40,
            file_date_time="2013-06-01T12:30:00",
            start_position=0,
            spectrum_type=3,
            lambda_=550.0,
            lambda_min=400.0,
            lambda_max=700.0,
            n_spectra=3,
            n_addtl_items=2,
            text_block_size=128,
            reserved=bytes(168),
        )

    def test_raise_exception_from_bytes(self) -> None:
        """
        Test :meth:`colour.io.tm2513.Header_IESTM2513.from_bytes` method
        raised exception.
        """

        with pytest.raises(IESTM2513Error):
            Header_IESTM2513.from_bytes(build_header()[:-1])

        with pytest.raises(IESTM2513Error):
            Header_IESTM2513.from_bytes(build_header() + b"\x00")

        with pytest.raises(IESTM2513Error):
            Header_IESTM2513.from_bytes(build_header(file_type=b"TM26"))

        for name in ("version", "n_spectra", "n_addtl_items", "text_block_size"):
            with pytest.raises(IESTM2513Error):
                Header_IESTM2513.from_bytes(build_header(**{name: -1}))

        with pytest.raises(IESTM2513Error):
            Header_IESTM2513.from_bytes(build_header(version=0))

        for spectrum_type in (-1, 5):
            with pytest.raises(IESTM2513Error):
                Header_IESTM2513.from_bytes(build_header(spectrum_type=spectrum_type))


class TestIES_TM2513_Sd:
    """
    Define :class:`colour.io.tm2513.SpectralDistribution_IESTM2513` class
    unit tests methods.
    """

    def test_required_attributes(self) -> None:
        """Test the presence of required attributes."""

        required_attributes = (
            "path",
            "header",
            "flags",
            "descriptions",
            "spectrum_index",
        )

        for attribute in required_attributes:
            assert attribute in dir(SpectralDistribution_IESTM2513)

    def test_required_methods(self) -> None:
        """Test the presence of required methods."""

        assert "read" in dir(SpectralDistribution_IESTM2513)

    def test_descriptions(self) -> None:
        """
        Test :attr:`colour.io.tm2513.SpectralDistribution_IESTM2513.\
descriptions` property.
        """

        sd = SpectralDistribution_IESTM2513(
            descriptions={"manufacturer": "Foo", "unknown": "Bar"}
        )

        assert tuple(sd.descriptions) == DESCRIPTION_FIELDS_IESTM2513
        assert sd.descriptions["manufacturer"] == "Foo"
        assert sd.descriptions["name"] == ""

        sd.descriptions = {"camera": "Baz"}

        assert tuple(sd.descriptions) == DESCRIPTION_FIELDS_IESTM2513
        assert sd.descriptions["camera"] == "Baz"
        assert sd.descriptions["manufacturer"] == ""

    def test_read(self, tmp_path: Path) -> None:
        """
        Test :meth:`colour.io.tm2513.SpectralDistribution_IESTM2513.read`
        method.
        """

        path = tmp_path / "tables.tm25"
        path.write_bytes(build_file([TABLE_A, TABLE_B, TABLE_C], name="Lamp"))

        sd = SpectralDistribution_IESTM2513(path)
        assert sd.read() is sd
        assert sd.path == str(path)
        assert sd.name == "Lamp (0)"
        assert sd.header.n_spectra == 3
        assert sd.flags.lum_flux
        xp_assert_close(sd.wavelengths, np.array([400.0, 500.0, 600.0, 700.0]))
        xp_assert_close(sd.values, np.array([0.125, 0.5, 0.875, 0.25]))

        sd = SpectralDistribution_IESTM2513(path, spectrum_index=2).read()
        assert sd.spectrum_index == 2
        xp_assert_close(sd.wavelengths, np.array([420.0, 520.0]))
        xp_assert_close(sd.values, np.array([1.0, 0.5]))

    def test_raise_exception_read(self, tmp_path: Path) -> None:
        """
        Test :meth:`colour.io.tm2513.SpectralDistribution_IESTM2513.read`
        method raised exception.
        """

        with pytest.raises(IESTM2513Error):
            SpectralDistribution_IESTM2513().read()

        path = tmp_path / "table.tm25"
        path.write_bytes(build_file([TABLE_A]))

        with pytest.raises(IESTM2513Error):
            SpectralDistribution_IESTM2513(path, spectrum_index=1).read()

        with pytest.raises(IESTM2513Error):
            SpectralDistribution_IESTM2513(path, spectrum_index=-1).read()

        path.write_bytes(build_file([]))

        with pytest.raises(IESTM2513Error):
            SpectralDistribution_IESTM2513(path).read()


class TestReadSpectralDistributionsTM2513:
    """
    Define :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
    definition unit tests methods.
    """

    def test_read_spectral_distributions_TM2513(self, tmp_path: Path) -> None:
        """
        Test :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        path = tmp_path / "Lamp.tm25"
        path.write_bytes(
            build_file(
                [TABLE_A, TABLE_B, TABLE_C],
                name="Lamp",
                manufacturer="Café Lumière",
                data_reference="Reference",
            )
        )

        sds = read_spectral_distributions_TM2513(path)

        assert len(sds) == 3
        assert len({id(sd) for sd in sds}) == 3
        assert [sd.spectrum_index for sd in sds] == [0, 1, 2]
        assert [sd.name for sd in sds] == ["Lamp (0)", "Lamp (1)", "Lamp (2)"]

        for sd, table in zip(sds, (TABLE_A, TABLE_B, TABLE_C), strict=True):
            assert isinstance(sd, SpectralDistribution_IESTM2513)
            assert sd.path == str(path)
            assert sd.header == sds[0].header
            assert sd.flags == sds[0].flags
            assert sd.descriptions == sds[0].descriptions
            xp_assert_close(sd.wavelengths, np.array([w for w, _ in table]))
            xp_assert_close(sd.values, np.array([v for _, v in table]))

        assert sds[0].header.n_spectra == 3
        assert sds[0].flags.as_tuple() == (
            True,
            True,
            True,
            False,
            True,
            False,
            False,
            False,
        )
        assert tuple(sds[0].descriptions) == DESCRIPTION_FIELDS_IESTM2513
        assert sds[0].descriptions["manufacturer"] == "Café Lumière"
        assert sds[0].descriptions["data_reference"] == "Reference"
        assert sds[0].descriptions["camera"] == ""

    def test_naming(self, tmp_path: Path) -> None:
        """
        Test the naming of the spectral distributions returned by the
        :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        path = tmp_path / "Unnamed.tm25"

        path.write_bytes(build_file([TABLE_A]))
        assert read_spectral_distributions_TM2513(path)[0].name == "Unnamed.tm25"

        path.write_bytes(build_file([TABLE_A], name="Lamp"))
        assert read_spectral_distributions_TM2513(path)[0].name == "Lamp"

    def test_description_nul_termination(self, tmp_path: Path) -> None:
        """
        Test that the description fields stop at their first NUL for the
        :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        data = bytearray(build_file([TABLE_A], name="Lamp"))
        offset = SIZE_HEADER_IESTM2513 + SIZE_FLAGS_IESTM2513
        data[offset + 4 * 6 : offset + 4 * 9] = "Xyz".encode("utf-32-le")

        path = tmp_path / "Lamp.tm25"
        path.write_bytes(bytes(data))

        assert read_spectral_distributions_TM2513(path)[0].descriptions["name"] == (
            "Lamp"
        )

    def test_spectral_tables_padding(self, tmp_path: Path) -> None:
        """
        Test that the spectral tables are read back to back and that the block
        is padded once, after the last table, by the
        :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        path = tmp_path / "Padded.tm25"

        assert len(build_spectral_tables([TABLE_B, TABLE_C, TABLE_A])) == 96

        path.write_bytes(build_file([TABLE_B, TABLE_C, TABLE_A]))

        sds = read_spectral_distributions_TM2513(path)

        assert [len(sd.wavelengths) for sd in sds] == [3, 2, 4]
        xp_assert_close(sds[0].wavelengths, np.array([450.0, 550.0, 650.0]))
        xp_assert_close(sds[1].wavelengths, np.array([420.0, 520.0]))
        xp_assert_close(sds[1].values, np.array([1.0, 0.5]))
        xp_assert_close(sds[2].wavelengths, np.array([400.0, 500.0, 600.0, 700.0]))
        xp_assert_close(sds[2].values, np.array([0.125, 0.5, 0.875, 0.25]))

        path.write_bytes(build_file([TABLE_B, TABLE_C]))
        sds = read_spectral_distributions_TM2513(path)

        assert len(sds) == 2
        xp_assert_close(sds[1].wavelengths, np.array([420.0, 520.0]))
        xp_assert_close(sds[1].values, np.array([1.0, 0.5]))

    def test_spectral_tables_padding_truncation(self, tmp_path: Path) -> None:
        """
        Test that a file truncated inside the padding of the spectral tables
        block raises an exception for the
        :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        path = tmp_path / "Truncated.tm25"
        data = build_file([TABLE_B, TABLE_C])

        path.write_bytes(data)
        assert len(read_spectral_distributions_TM2513(path)) == 2

        path.write_bytes(data[:-1])
        with pytest.raises(IESTM2513Error):
            read_spectral_distributions_TM2513(path)

        path.write_bytes(data[:-16])
        with pytest.raises(IESTM2513Error):
            read_spectral_distributions_TM2513(path)

    def test_trailing_data(self, tmp_path: Path) -> None:
        """
        Test that the data following the spectral tables is ignored by the
        :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition.
        """

        path = tmp_path / "Trailing.tm25"
        path.write_bytes(build_file([TABLE_A]) + b"\xff" * 100)

        assert len(read_spectral_distributions_TM2513(path)) == 1

    def test_raise_exception_read_spectral_distributions_TM2513(
        self, tmp_path: Path
    ) -> None:
        """
        Test :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition raised exception.
        """

        path = tmp_path / "Malformed.tm25"
        data = build_file([TABLE_B, TABLE_C])

        flags_end = SIZE_HEADER_IESTM2513 + SIZE_FLAGS_IESTM2513
        descriptions_end = flags_end + 9 * SIZE_DESCRIPTION_FIELD_IESTM2513
        table_b_end = descriptions_end + 4 + 8 * len(TABLE_B)

        truncations = (
            SIZE_HEADER_IESTM2513 - 1,
            SIZE_HEADER_IESTM2513 + 16,
            flags_end + 100,
            descriptions_end + 2,
            descriptions_end + 20,
            table_b_end - 1,
            table_b_end + 3,
            len(data) - 1,
        )

        for size in truncations:
            path.write_bytes(data[:size])
            with pytest.raises(IESTM2513Error):
                read_spectral_distributions_TM2513(path)

        path.write_bytes(b"NOPE" + data[4:])
        with pytest.raises(IESTM2513Error):
            read_spectral_distributions_TM2513(path)

        flags = bytearray(data)
        flags[SIZE_HEADER_IESTM2513 + 8 : SIZE_HEADER_IESTM2513 + 12] = struct.pack(
            "<i", 2
        )
        path.write_bytes(bytes(flags))
        with pytest.raises(IESTM2513Error):
            read_spectral_distributions_TM2513(path)

        for count in (-3, 0):
            invalid = bytearray(data)
            invalid[descriptions_end : descriptions_end + 4] = struct.pack("<i", count)
            path.write_bytes(bytes(invalid))
            with pytest.raises(IESTM2513Error):
                read_spectral_distributions_TM2513(path)

    def test_sample_file(self) -> None:
        """
        Test :func:`colour.io.tm2513.read_spectral_distributions_TM2513`
        definition with the sample file.
        """

        sds = read_spectral_distributions_TM2513(TM25_SAMPLE_FILE)

        assert len(sds) == 2
        assert sds[0].descriptions["name"] == "Sample Lamp"
        xp_assert_close(sds[0].wavelengths, np.array([400.0, 550.0, 700.0]))
        xp_assert_close(sds[1].values, np.array([0.1, 0.4, 0.6, 1.0, 0.3]), atol=1e-6)
