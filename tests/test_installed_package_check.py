"""Regression coverage for the installed-package check's source import guard."""

from email.message import Message

import pytest

from scripts import check_installed_package as installed_check


@pytest.fixture
def check_import_location(monkeypatch, tmp_path):
    checkout = tmp_path / "checkout"
    monkeypatch.setattr(
        installed_check, "__file__",
        str(checkout / "scripts" / "check_installed_package.py"),
    )
    package_metadata = Message()
    package_metadata["Author"] = "Denis Sivagin"
    package_metadata["License-Expression"] = "MIT"
    package_metadata["Project-URL"] = "Author, https://github.com/Denissvgn"
    monkeypatch.setattr(installed_check, "metadata", lambda name: package_metadata)

    def check(package_file):
        monkeypatch.setattr(installed_check.html_to_pdf, "__file__", str(package_file))
        installed_check.InstalledPackageTests(
            "test_distribution_metadata_and_import_location"
        ).test_distribution_metadata_and_import_location()

    return checkout, check


@pytest.mark.parametrize("location", ["local-venv", "external-venv", "similar-name"])
def test_accepts_installed_package_locations(check_import_location, location):
    checkout, check = check_import_location
    if location == "local-venv":
        package = checkout / ".venv" / "lib" / "python3.12" / "site-packages" / "html_to_pdf"
    elif location == "external-venv":
        package = checkout.parent / "venv" / "lib" / "python3.12" / "site-packages" / "html_to_pdf"
    else:
        package = checkout / "html_to_pdf_copy"
    check(package / "__init__.py")


def test_rejects_source_tree_import(check_import_location):
    checkout, check = check_import_location
    with pytest.raises(AssertionError):
        check(checkout / "html_to_pdf" / "__init__.py")


def test_rejects_source_tree_import_through_symlink(check_import_location):
    checkout, check = check_import_location
    source = checkout / "html_to_pdf"
    source.mkdir(parents=True)
    (source / "__init__.py").touch()
    linked_package = checkout.parent / "linked-package"
    linked_package.symlink_to(source, target_is_directory=True)
    with pytest.raises(AssertionError):
        check(linked_package / "__init__.py")
