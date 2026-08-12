import ftplib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import pystac
import requests
from pydantic import BaseModel, ValidationError

from eozilla_eoap.procolike import LocalArtifactManager
from eozilla_eoap.procolike.eoap_artifact_manager import WrappedFtpUrl, WrappedHttpUrl
from eozilla_eoap.procolike.eoap_process import Directory, File


class NoStagingRequiredProcess(BaseModel):
    a: int


class FileStagingRequiredProcess(BaseModel):
    f: File


class DirectoryStaingRequiredProcess(BaseModel):
    d: Directory


class MixedStagingrequiredProcess(BaseModel):
    a: int
    f: File
    d: Directory


def log_file_lookalike(log_dir: Path) -> Path:
    with open(Path(log_dir, "log.run"), "wt") as f:
        f.writelines(
            [
                "Lorem ipsum dolor sit amet,",
                "consectetur adipiscing elit,",
                "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
                "Ut enim ad minim veniam,",
                "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
                "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
                "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
            ]
        )

    return Path(log_dir, "log.run")


class LocalArtifactManagerTest(TestCase):
    def test_intialize_creates_directories(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()

            self.assertEqual(
                Path(tdir, "static-job-id-1"), manager.persistent_output_directory
            )
            self.assertTrue(Path(manager.persistent_output_directory, "out").exists())
            self.assertTrue(Path(manager.persistent_output_directory, "log").exists())
            self.assertTrue(Path(manager.temporary_output_directory, "out").exists())
            self.assertTrue(Path(manager.temporary_output_directory, "log").exists())

            # NOTE: assuming here that deletion already works,
            #       otherwise I would need to remove directories created manually

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_http_success(self, mock_load_http):
        mock_load_http.return_value = "/some/local/file/path/to/downloaded/file.txt"

        process_instance_model = FileStagingRequiredProcess(
            f="http://fileserver.example.com/path/to/some/file.txt"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_http.assert_called_once()
            mock_load_http.assert_called_with(
                WrappedHttpUrl("http://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_http_error(self, mock_load_http):
        mock_load_http.side_effect = requests.exceptions.HTTPError

        process_instance_model = FileStagingRequiredProcess(
            f="http://fileserver.example.com/path/to/some/file.txt"
        )

        with (
            TemporaryDirectory() as tdir,
            self.assertRaises(requests.exceptions.HTTPError),
        ):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_http.assert_called_once()
            mock_load_http.assert_called_with(
                WrappedHttpUrl("http://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_http_timeout(self, mock_load_http):
        mock_load_http.side_effect = requests.exceptions.Timeout

        process_instance_model = FileStagingRequiredProcess(
            f="http://fileserver.example.com/path/to/some/file.txt"
        )

        with (
            TemporaryDirectory() as tdir,
            self.assertRaises(requests.exceptions.Timeout),
        ):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_http.assert_called_once()
            mock_load_http.assert_called_with(
                WrappedHttpUrl("http://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_https_success(self, mock_load_https):
        mock_load_https.return_value = "/some/local/file/path/to/downloaded/file.txt"

        process_instance_model = FileStagingRequiredProcess(
            f="https://fileserver.example.com/path/to/some/file.txt"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_https.assert_called_once()
            mock_load_https.assert_called_with(
                WrappedHttpUrl("https://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_https_error(self, mock_load_https):
        mock_load_https.side_effect = requests.exceptions.HTTPError

        process_instance_model = FileStagingRequiredProcess(
            f="https://fileserver.example.com/path/to/some/file.txt"
        )

        with (
            TemporaryDirectory() as tdir,
            self.assertRaises(requests.exceptions.HTTPError),
        ):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_https.assert_called_once()
            mock_load_https.assert_called_with(
                WrappedHttpUrl("https://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_https_timeout(self, mock_load_https):
        mock_load_https.side_effect = requests.exceptions.Timeout

        process_instance_model = FileStagingRequiredProcess(
            f="https://fileserver.example.com/path/to/some/file.txt"
        )

        with (
            TemporaryDirectory() as tdir,
            self.assertRaises(requests.exceptions.Timeout),
        ):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_https.assert_called_once()
            mock_load_https.assert_called_with(
                WrappedHttpUrl("https://fileserver.example.com/path/to/some/file.txt")
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_ftp_success(self, mock_load_ftp):
        mock_load_ftp.return_value = "/some/local/file/path/to/downloaded/file.txt"

        process_instance_model = FileStagingRequiredProcess(
            f="ftp://fileserver.example.com/path/to/some/file.txt"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_ftp.assert_called_once()
            mock_load_ftp.assert_called_with(
                WrappedFtpUrl(
                    username="",
                    password="",
                    server="fileserver.example.com",
                    path="/path/to/some/file.txt",
                )
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_ftp_auth(self, mock_load_ftp):
        mock_load_ftp.return_value = "/some/local/file/path/to/downloaded/file.txt"

        process_instance_model = FileStagingRequiredProcess(
            f="ftp://user:password@fileserver.example.com/path/to/some/file.txt"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_ftp.assert_called_once()
            mock_load_ftp.assert_called_with(
                WrappedFtpUrl(
                    username="user",
                    password="password",  # noqa: S106
                    server="fileserver.example.com",
                    path="/path/to/some/file.txt",
                )
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_ftp_auth_failure(self, mock_load_ftp):
        mock_load_ftp.side_effect = ftplib.error_perm

        process_instance_model = FileStagingRequiredProcess(
            f="ftp://user:wrong_password@ileserver.example.com/path/to/some/file.txt"
        )

        with TemporaryDirectory() as tdir, self.assertRaises(ftplib.error_perm):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_ftp.assert_called_once()
            mock_load_ftp.assert_called_with(
                WrappedFtpUrl(
                    username="user",
                    password="wrong_password",  # noqa: S106
                    server="fileserver.example.com",
                    path="/path/to/some/file.txt",
                )
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._dispatch_singular_file_download"
    )
    def test_stage_in_ftp_file_not_found(self, mock_load_ftp):
        mock_load_ftp.side_effect = ftplib.error_perm

        process_instance_model = FileStagingRequiredProcess(
            f="ftp://user:password@fileserver.example.com/path/to/non-existent/some/file.txt"
        )

        with TemporaryDirectory() as tdir, self.assertRaises(ftplib.error_perm):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_files()

            mock_load_ftp.assert_called_once()
            mock_load_ftp.assert_called_with(
                WrappedFtpUrl(
                    username="user",
                    password="password",  # noqa: S106
                    server="fileserver.example.com",
                    path="/path/to/some/file.txt",
                )
            )

            self.assertEqual(len(manager.staged_in_files), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["f"]
            local_model = File(**local_catalog_path)
            self.assertIsInstance(local_model, File)
            self.assertEqual(
                "/some/local/file/path/to/downloaded/file.txt", local_model.location
            )

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._load_remote_stac_from_http_url"
    )
    def test_stage_in_stac_item(self, mock_load_stac):
        item = pystac.Item(
            id="test-item",
            geometry=None,
            bbox=None,
            datetime=datetime.now(timezone.utc),
            properties={},
        )

        mock_load_stac.return_value = item

        process_instance_model = DirectoryStaingRequiredProcess(
            d="https://stac.example.com/stac-item"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_directories()

            mock_load_stac.assert_called_once()
            mock_load_stac.assert_called_with("https://stac.example.com/stac-item")

            self.assertEqual(len(manager.staged_in_directories), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["d"]
            local_model = Directory(**local_catalog_path)
            self.assertIsInstance(local_model, Directory)
            self.assertTrue(Path(local_model.location).is_dir())
            self.assertTrue(Path(local_model.location).exists())
            self.assertTrue(Path(local_model.location, "catalog.json").exists())

            catalog = pystac.STACObject.from_file(
                Path(local_model.location, "catalog.json")
            )
            self.assertIsNone(pystac.validation.validate_all(catalog))

            shutil.rmtree(local_model.location)

    @patch(
        "eozilla_eoap.procolike.eoap_artifact_manager._load_remote_stac_from_http_url"
    )
    def test_stage_in_stac_itemcollection(self, mock_load_stac):
        item = pystac.Item(
            id="test-item",
            geometry=None,
            bbox=None,
            datetime=datetime.now(timezone.utc),
            properties={},
        )

        item_collection = pystac.ItemCollection(
            [item],
        )

        mock_load_stac.return_value = item_collection

        process_instance_model = DirectoryStaingRequiredProcess(
            d="https://stac.example.com/stac-item"
        )

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                process_instance_model,
            )

            manager.initialize()
            manager.stage_in_directories()

            mock_load_stac.assert_called_once()
            mock_load_stac.assert_called_with("https://stac.example.com/stac-item")

            self.assertEqual(len(manager.staged_in_directories), 1)

            rebuild_process_arguments = manager.rebuild_process_arguments()
            self.assertIsInstance(rebuild_process_arguments, dict)
            self.assertEqual(len(rebuild_process_arguments), 1)

            local_catalog_path = rebuild_process_arguments["d"]
            local_model = Directory(**local_catalog_path)
            self.assertIsInstance(local_model, Directory)
            self.assertTrue(Path(local_model.location).is_dir())
            self.assertTrue(Path(local_model.location).exists())
            self.assertTrue(Path(local_model.location, "catalog.json").exists())

            catalog = pystac.STACObject.from_file(
                Path(local_model.location, "catalog.json")
            )
            self.assertIsNone(pystac.validation.validate_all(catalog))

            shutil.rmtree(local_model.location)

    def test_stage_in_error_unsupported_protocol(self):
        with TemporaryDirectory() as tdir, self.assertRaises(NotImplementedError):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                FileStagingRequiredProcess(
                    f="s3://fileserver.example.com/path/to/file.txt"
                ),
            )
            manager.initialize()
            manager.stage_in()

    def test_stage_in_error_missing_protocol(self):
        with TemporaryDirectory() as tdir, self.assertRaises(ValidationError):
            manager = LocalArtifactManager(
                Path(tdir),
                "static-job-id-1",
                FileStagingRequiredProcess(
                    f="/fileserver.example.com/path/to/file.txt"
                ),
            )
            manager.initialize()
            manager.stage_in()

    def test_stage_in_no_staging_required(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            manager.stage_in()

            self.assertEqual({}, manager.staged_in_directories)
            self.assertEqual({}, manager.staged_in_files)
            self.assertEqual(
                NoStagingRequiredProcess(a=3), manager.process_instance_model
            )

    # TODO: these should be asserted in stage-in tests as they actually
    #       require stage-in
    def test_rebuilding_replaces_file(self): ...

    # TODO: these should be asserted in stage-in tests as they actually
    #       require stage-in
    def test_rebuilding_replaces_directory(self): ...

    def test_rebuilding_identity_without_staging(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            manager.stage_in()

            self.assertEqual(
                NoStagingRequiredProcess(a=3).model_dump(),
                manager.rebuild_process_arguments(),
            )

    def test_stage_out(self):
        self.skipTest(
            "LocalArtifactManager.stage_out only bundles stage-out of log files and entries in temporary output directory."
        )

    def test_stage_out_no_arg_staging_required(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            manager.stage_in()

            new_results = manager.stage_out({"some_result": 3.141})

            self.assertDictEqual({"some_result": 3.141}, new_results)

    def test_stage_out_file(self):
        temporary_output_file = NamedTemporaryFile(suffix=".txt")
        boilerplate_result = {
            "test_out": {
                "location": f"file://{temporary_output_file.name}",
                "basename": Path(temporary_output_file.name).name,
                "class": "File",
                "checksum": "sha1$648a6a6ffffdaa0badb23b8baf90b6168dd16b3a",
                "size": 12,
                "path": temporary_output_file.name,
            }
        }

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            # TODO: call file-specific method
            patched_result = manager.stage_out(boilerplate_result)

            self.assertEqual(len(patched_result), 1)
            self.assertEqual(boilerplate_result.keys(), patched_result.keys())
            self.assertTrue(Path(patched_result["test_out"]).exists())
            self.assertEqual(Path(patched_result["test_out"]).parent.name, "out")

            self.assertEqual(len(manager.staged_out_files), 1)
            self.assertIn(patched_result["test_out"], manager.staged_out_files.items())

        temporary_output_file.close()

    def test_stage_out_nested_file(self):
        temporary_subdirectory = TemporaryDirectory(
            prefix="temporary-testing-subdirectory-"
        )
        temporary_output_file = NamedTemporaryFile(
            dir=temporary_subdirectory.name, suffix=".txt"
        )
        boilerplate_result = {
            "test_out": {
                "location": f"file://{temporary_output_file.name}",
                "basename": Path(temporary_output_file.name).name,
                "class": "File",
                "checksum": "sha1$648a6a6ffffdaa0badb23b8baf90b6168dd16b3a",
                "size": 12,
                "path": temporary_output_file.name,
            }
        }

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            # TODO: call file-specific method!
            patched_result = manager.stage_out(boilerplate_result)

            self.assertEqual(len(patched_result), 1)
            self.assertEqual(boilerplate_result.keys(), patched_result.keys())
            self.assertTrue(Path(patched_result["test_out"]).exists())
            self.assertEqual(Path(patched_result["test_out"]).parent.parent.name, "out")

            self.assertEqual(len(manager.staged_out_files), 1)
            self.assertIn(patched_result["test_out"], manager.staged_out_files.items())

        temporary_output_file.close()
        temporary_subdirectory.cleanup()

    def test_stage_out_stac(self):
        stac_output = Path(Path(__file__).parent.parent, "resources", "example-stac")

        boilerplate_result = {
            "test_out": {
                "class": "Directory",
                "location": f"file://{stac_output}",
                "basename": "example-stac",
                "listings": {},
                "path": str(stac_output),
            }
        }

        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            # TODO: call stac-specific method
            patched_result = manager.stage_out(boilerplate_result)

            self.assertEqual(len(patched_result), 1)
            self.assertEqual(boilerplate_result.keys(), patched_result.keys())

            # check correct nesting/structure
            self.assertEqual(Path(patched_result["test_out"]).parent.parent.name, "out")
            self.assertEqual(len(manager.staged_out_directories), 1)
            self.assertIn(
                patched_result["test_out"], manager.staged_out_directories.items()
            )

            # check existence of assets/catalog related files
            catalog_base_dir = Path(patched_result["test_out"]).parent
            self.assertTrue(catalog_base_dir.exists())
            self.assertTrue(Path(patched_result["test_out"]).exists())
            self.assertTrue(
                Path(
                    catalog_base_dir,
                    "S2B_10TFK_20210713_0_L2A",
                    "S2B_10TFK_20210713_0_L2A.json",
                ).exists()
            )
            self.assertTrue(
                Path(catalog_base_dir, "S2B_10TFK_20210713_0_L2A", "otsu.tif").exists()
            )

            # no files other than those comprising the STAC catalog should be present in output
            # in case the process produces "dirty" output
            self.assertEqual(
                list(
                    manager.persistent_output_directory.rglob("*should-not-be-copied*")
                ),
                [],
            )

            # validate STAC catalog itself
            catalog = pystac.STACObject.from_file(patched_result["test_out"])
            self.assertIsNone(pystac.validation.validate_all(catalog))

    def test_stage_out_logs_success(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            manager.stage_in()

            lfile = log_file_lookalike(Path(manager.temporary_output_directory, "log"))

            _ = manager.stage_out({})

            lfile.unlink()
            self.assertEqual(len(manager.staged_out_directories), 1)
            self.fail("Compare hash values of file contents")

    def test_remove_staged_inputs(self):
        self.skipTest(
            "LocalArtifactManager.remove_staged_input only bundles removal of staged-in files and STACs."
        )

    def test_remove_staged_in_files(self):
        with (
            TemporaryDirectory() as tdir,
            TemporaryDirectory() as tdir2,
        ):
            if1 = NamedTemporaryFile(dir=tdir2, suffix=".txt")
            if2 = NamedTemporaryFile(dir=tdir2, suffix=".txt")

            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            # Skipping actual stage-in as it's not what should be tested
            manager.staged_in_files = {
                "input-1": [Path(if1.name)],
                "input-2": [Path(if2.name)],
            }

            manager.remove_staged_in_files()

            self.assertFalse(Path(if1.name).exists())
            self.assertFalse(Path(if2.name).exists())
            self.assertEqual(manager.staged_in_files, {})

            if1.close()
            if2.close()

    def test_remove_staged_in_directories(self):
        with (
            TemporaryDirectory() as tdir,
            TemporaryDirectory() as tdir2,
        ):
            id1 = TemporaryDirectory(dir=tdir2, delete=False)
            id2 = TemporaryDirectory(dir=tdir2, delete=False)

            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()
            # Skipping actual stage-in as it's not what should be tested
            manager.staged_in_directories = {
                "input-1": [Path(id1.name)],
                "input-2": [Path(id2.name)],
            }

            manager.remove_staged_in_directories()

            self.assertFalse(Path(id1.name).exists())
            self.assertFalse(Path(id2.name).exists())
            self.assertEqual(manager.staged_in_directories, {})

            id1.cleanup()
            id2.cleanup()

    def test_remove_temporary_outputs(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()

            kept_temporary_dir = manager.temporary_output_directory

            manager.remove_temporary_outputs()

            self.assertFalse(Path(kept_temporary_dir, "out").exists())
            self.assertFalse(Path(kept_temporary_dir, "log").exists())
            self.assertFalse(Path(kept_temporary_dir).exists())

    def test_remove_persistent_outputs(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()

            kept_persistent_dir = manager.persistent_output_directory

            manager.remove_persistent_outputs()

            self.assertFalse(Path(kept_persistent_dir, "out").exists())
            self.assertFalse(Path(kept_persistent_dir, "log").exists())
            self.assertFalse(Path(kept_persistent_dir).exists())

    def test_deletion_removes_trees(self):
        with TemporaryDirectory() as tdir:
            manager = LocalArtifactManager(
                Path(tdir), "static-job-id-1", NoStagingRequiredProcess(a=3)
            )
            manager.initialize()

            kept_persistent_dir = manager.persistent_output_directory
            kept_temporary_dir = manager.temporary_output_directory

            # TODO: do some actual stage-in to populate dicts of staged-in files and directories

            del manager

            self.assertFalse(Path(kept_persistent_dir, "out").exists())
            self.assertFalse(Path(kept_persistent_dir, "log").exists())
            self.assertFalse(Path(kept_persistent_dir).exists())
            self.assertFalse(Path(kept_temporary_dir, "out").exists())
            self.assertFalse(Path(kept_temporary_dir, "log").exists())
            self.assertFalse(Path(kept_temporary_dir).exists())
