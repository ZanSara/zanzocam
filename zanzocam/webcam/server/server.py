from typing import Any, List, Dict, Optional

import os
import json
import shutil
import datetime
import requests
from ftplib import FTP, FTP_TLS, error_perm
from json import JSONDecodeError

from constants import *
from webcam.utils import log, log_error, log_row
from webcam.configuration import Configuration
from webcam.server.http_server import HttpServer
from webcam.server.ftp_server import FtpServer
from webcam.errors import ServerError, UnexpectedServerResponse



class Server:
    """
    Handles all communications with the server.
    """
    def __init__(self, server_settings: Dict):

        if not server_settings:
            raise ServerError("No server information found in the "
                "configuration file.")
        
        try:
            self.protocol = server_settings.get("protocol", None)
        # Occurs if 'parameters' is not a dict, like {'server': 'not a dict'}
        except AttributeError:
            self.protocol = None

        # Protect against protocol not being a string, where upper() would fail
        self.protocol = str(self.protocol).upper()

        if self.protocol.upper() == "HTTP":
            self._server = HttpServer(server_settings)
            
        elif self.protocol.upper() == "FTP":
            self._server = FtpServer(server_settings)

        else:
            raise ServerError("The communication protocol with "
                "the server (HTTP, FTP) was not specified. "
                "No protocol is available to estabilish a "
                "connection to the server.")

    def get_endpoint(self):
        """
        Return a 'server agnostic' endpoint for logging purposes.
        """
        if self.protocol == "FTP":
            return f"ftp://{self._server.username}@{self._server.hostname}"
        elif self.protocol == "HTTP":
            return f"{self._server.url}"
        else:
            raise ValueError("No protocol defined, cannot render endpoint.")

    def update_configuration(self, old_configuration: Configuration, 
            new_conf_path : Path = CONFIGURATION_FILE) -> Configuration:
        """
        Download the new configuration file from the server and updates it
        locally.
        """
        # Get the new configuration from the server
        configuration_data = self._server.download_new_configuration()
        
        # If the old server replied something good, it's OK to backup its data.
        old_configuration.backup()

        # Create new configuration object (overwrites configuration.json)
        configuration = Configuration.create_from_dictionary(
            configuration_data, path=new_conf_path)

        return configuration

    def download_overlay_images(self, images_list: List[str]) -> None:
        """ 
        Download all the overlay images that should be re-downloaded.
        If it fails, logs it and replaces that image with a transparent pixel, 
        to avoid adding checks later in the processing.
        """
        for image_name in images_list:
            try:
                self._server.download_overlay_image(image_name)

            except Exception as e:
                log_error(f"New overlay image failed to download: "
                          f"'{image_name}'. Ignoring it. This overlay "
                          f"image will not appear on the final image.", e)

    def upload_logs(self, path: Path = CAMERA_LOG):
        """ 
        Send the logs to the server.
        """
        # NOTE: exceptions in here should NOT escalate. Catch everything!!
        self._server.send_logs(path)
        # Clear the logs once they have been uploaded
        with open(path, "w") as l:
            pass


    def upload_diagnostics(self, path: Path = DIAGNOSTICS_LOG):
        """ 
        Send a diagnostic report to the server.
        """
        # NOTE: exceptions in here should NOT escalate. Catch everything!!
        # FIXME for now they get sent as regular logs (they even have the same name!). Handle better later on.
        try:
            self._server.send_logs(path)
            # Clear the logs once they have been uploaded
            with open(path, "w") as l:
                pass
            log(f"Diagnostics log uploaded successfully to {self._server.endpoint}")
            
        except Exception as e:
            log_error(f"Something happened while uploading the diagnostics log to {self._server.endpoint} "
                      "This error will be ignored.", e)
            return

    
    def upload_failure_report(self, wrong_conf: Dict[str, Any], 
            right_conf: Dict[str, Any], logs_path: Path = CAMERA_LOG, ) -> None:
        """ 
        Send a report of the failure to the old server.
        """
        logs = ""
        try:
            if os.path.exists(logs_path):
                with open(logs_path, "r") as l:
                    logs = l.read()
        except Exception as e:
            log_error("Something went wrong opening the logs file."
                      "The report will contain no logs.", e)
            logs = "An error occurred opening the logs file and the logs " \
                   "could not be read."

        if not logs or logs == "":
            logs = " ==> No logs found <== "
        
        with open(FAILURE_REPORT_PATH, "w") as report:
            report.write(
                "**********************\n"
                "*   FAILURE REPORT   *\n"
                "**********************\n" 
                "Failed to use the server information contained in the new "
                "configuration file.\n"
                "New, NOT working server information is the following:\n" +
                json.dumps(wrong_conf, indent=4) +
                "\nPlease fix the above information in the configuration "
                "file or fix the affected server.\n"
                "ZANZOCAM will keep trying to download a new config with "
                "this parameters instead:\n" +
                json.dumps(right_conf, indent=4) +
                "\nHere below is the log of the last run before the crash.\n\n"
                "**********************\n\n" +
                logs +
                "\n\n**********************\n"
            )

        # Send the logs
        self._server.send_logs(FAILURE_REPORT_PATH)


    def upload_picture(self, image_path: Path, image_name: str, 
                       image_extension: str, cleanup: bool = True) -> None:
        """
        Uploads the new picture to the server.
        """
        # Note: Errors here MUST escalate
        
        if not os.path.exists(image_path):
            raise ValueError(f"No picture to upload: {image_path} does not exist")
            
        if not image_name or not image_path or not image_extension:
            raise ValueError(f"Cannot upload the picture: picture name ({image_name}) " 
                      f"or location ({image_path}) or extension ({image_extension}) "
                      f"not given.")
        
        # Make sure the file in question exists
        if not os.path.exists(image_path):
            raise ValueError(f"Cannot upload the picture: {image_path} does not exist.")

        # Upload the picture
        self.final_image_path = self._server.upload_picture(image_path, image_name, image_extension)
        log(f"Picture {self.final_image_path.name} uploaded successfully.")

        if cleanup and os.path.exists(self.final_image_path):
            os.remove(self.final_image_path)
            log("Uploaded image wes removed from disk successfully.")
