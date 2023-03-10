#!/usr/bin/env python3

### IMPORTS ###
import json
import logging
import os
import subprocess

### GLOBALS ###

### FUNCTIONS ###
def get_images_from_payload(payload_json):
    logging.debug("Getting images from the payload")
    logging.debug("  tmp_payload_json: %s", payload_json)
    tmp_payload_dict = json.loads(payload_json)
    logging.debug("  tmp_payload_dict: %s", tmp_payload_dict)
    tmp_images = []
    if 'image' in tmp_payload_dict.keys():
        tmp_images.append(str(tmp_payload_dict['image']))
    if 'images' in tmp_payload_dict.keys():
        for tmp_img in tmp_payload_dict['images']:
            tmp_images.append(str(tmp_img))
    logging.debug("  tmp_images: %s", tmp_images)
    return tmp_images

def docker_login(login_data):
    logging.debug("Logging into Docker CLI")
    tmp_prep_cmd = "docker login -u {} -p {} {}".format(
        login_data['user'],
        login_data['apikey'],
        login_data['docker_url']
    )
    logging.debug("  tmp_prep_cmd: %s", tmp_prep_cmd)
    tmp_prep_output = subprocess.run(
        tmp_prep_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE
    )
    if tmp_prep_output.returncode == 0:
        logging.debug("  Successfully logged into docker")
    else:
        logging.warning("Failed to log into docker: %s", tmp_prep_output.stderr)

### CLASSES ###
class DockerImagePuller:
    # NOTE: This script currently only supports the amd64 type of docker images.
    #       It is possible to extend this script to support arm and others.
    SUPPORTED_ARCHITECTURES = ['amd64']

    def __init__(self, login_data, docker_image):
        self.logger = logging.getLogger(type(self).__name__)
        self.login_data = login_data
        self.docker_image = docker_image
        self.local_repo = login_data['local_repo']
        self.image_tag = self.docker_image.split(':')
        self.image_split = self.image_tag[0].split('/')
        self.manifest = None
        self.docker_version = None
        self.success_pull = False
        self.success_copy = False
        self.logger.debug("DockerImagePuller for image: %s", docker_image)

    def _arti_curl_copy(self, input_from, input_to):
        # FIXME: Convert this to urllib or similar
        self.logger.debug("Copying artifact from: %s to: %s", input_from, input_to)
        curl_cmd = "curl -f -XPOST -u{}:{} {}/api/copy/{}?to=/{}".format(
            self.login_data['user'],
            self.login_data['apikey'],
            self.login_data['arti_url'],
            input_from,
            input_to
        )
        curl_output = subprocess.run(curl_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.logger.debug("  curl_output: %s", curl_output)
        # FIXME: Raise exceptions for errors, in particular, the '409: Conflict' error
        # FIXME: There still seems to be issues with 409: Conflict errors, even if there wasn't already an image copied.
        return curl_output

    def _arti_curl_get(self, input_url):
        # FIXME: Convert this to urllib or similar
        self.logger.debug("Get artifact: %s", input_url)
        curl_cmd = "curl -f -u{}:{} {}/{}".format(
            self.login_data['user'],
            self.login_data['apikey'],
            self.login_data['arti_url'],
            input_url
        )
        curl_output = subprocess.run(curl_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.logger.debug("  curl_output: %s", curl_output)
        # FIXME: Raise exceptions for errors, in particular, the '409: Conflict' error
        return curl_output

    def _pull_image(self):
        self.logger.debug("Pulling the docker image: %s", self.docker_image)
        tmp_pull_cmd = "docker pull {}".format(self.docker_image)
        tmp_pull_output = subprocess.run(tmp_pull_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        self.logger.debug("  tmp_pull_output: %s", tmp_pull_output)
        if tmp_pull_output.returncode == 0:
            self.logger.debug("  Successfully pulled '%s'", self.docker_image)
            self.success_pull = True
        else:
            # FIXME: Should this raise an exception on failure?
            self.logger.warning("Failed to pull image '%s' with error: %s", self.docker_image, tmp_pull_output.stderr)

    def _pull_manifest(self):
        self.logger.debug("Pulling the manifest for image: %s", self.docker_image)
        self.logger.debug("tmp_image_tag: %s", self.image_tag)
        self.logger.debug("tmp_image_split: %s", self.image_split)
        tmp_image_arti_name = "{}/{}/{}/{}/list.manifest.json".format(
            self.image_split[1],
            self.image_split[2],
            self.image_split[3],
            self.image_tag[1]
        )
        tmp_curl1_output = self._arti_curl_get(tmp_image_arti_name)
        self.logger.debug("  tmp_curl1_output: %s", tmp_curl1_output)
        if tmp_curl1_output.returncode == 0:
            # Succeeded in pulling the V2 type image manifest.
            self.manifest = json.loads(tmp_curl1_output.stdout.decode())
            self.docker_version = "V2"
        else:
            # Failure in pulling V2, so try V1
            tmp_image_arti_name = "{}/{}/{}/{}/manifest.json".format(
                self.image_split[1],
                self.image_split[2],
                self.image_split[3],
                self.image_tag[1]
            )
            tmp_curl12_output = self._arti_curl_get(tmp_image_arti_name)
            self.logger.debug("  tmp_curl12_output: %s", tmp_curl12_output)
            if tmp_curl12_output.returncode == 0:
                # Succeeded in pulling the V1 type image manifest.
                self.manifest = json.loads(tmp_curl12_output.stdout.decode())
                self.docker_version = "V1"
            else:
                # FIXME: Raise an exception if both manifest pull attempts fail
                self.logger.warning("Failed to pull a manifest")

    def _copy_v1(self):
        self.logger.debug("Copying the V1 type docker image")
        tmp_config_from_name = "{}/{}/{}/{}".format(
            self.image_split[1],
            self.image_split[2],
            self.image_split[3],
            "__".join(self.manifest['config']['digest'].split(':'))
        )
        self.logger.debug("tmp_config_from_name: %s", tmp_config_from_name)
        tmp_config_to_name = "{}/{}/{}/{}".format(
            self.local_repo,
            self.image_split[2],
            self.image_split[3],
            "__".join(self.manifest['config']['digest'].split(':'))
        )
        self.logger.debug("tmp_config_to_name: %s", tmp_config_to_name)
        tmp_curl13_output = self._arti_curl_copy(tmp_config_from_name, tmp_config_to_name)
        self.logger.debug("tmp_curl13_output: %s", tmp_curl13_output)
        if tmp_curl13_output.returncode != 0:
            # Failed to copy the config
            # FIXME: What error handling should happen here?
            # FIXME: The '409: Conflict' error means the file has already been copied,
            #        likely from a previous curation.
            # FIXME: Still getting '409: Conflict' errors when the image hasn't already been copied.  Directories?
            self.logger.debug("Successfully copied config")
        # Copy the layer files
        for tmp_sublayer in self.manifest['layers']:
            tmp_layer_from_name = "{}/{}/{}/{}".format(
                self.image_split[1],
                self.image_split[2],
                self.image_split[3],
                "__".join(tmp_sublayer['digest'].split(':'))
            )
            self.logger.debug("tmp_layer_from_name: %s", tmp_layer_from_name)
            tmp_layer_to_name = "{}/{}/{}/{}".format(
                self.local_repo,
                self.image_split[2],
                self.image_split[3],
                "__".join(tmp_sublayer['digest'].split(':'))
            )
            self.logger.debug("tmp_layer_to_name: %s", tmp_layer_to_name)
            tmp_curl14_output = self._arti_curl_copy(tmp_layer_from_name, tmp_layer_to_name)
            self.logger.debug("tmp_curl14_output: %s", tmp_curl14_output)
            if tmp_curl14_output.returncode != 0:
                # Failed to copy the config
                # FIXME: What error handling should happen here?
                # FIXME: The '409: Conflict' error means the file has already been copied, likely from a previous
                #        curation.
                # FIXME: Still getting '409: Conflict' errors when the image hasn't already been copied.  Directories?
                self.logger.debug("Successfully copied layer")
        logging.debug("Completed Copying V1 Images")

    def _copy_v2(self):
        self.logger.debug("Copying the V2 type docker image")
        sub_images = self.manifest['manifests']
        self.logger.debug("sub_images: %s", sub_images)
        for subimage in sub_images:
            if subimage['platform']['architecture'] in self.SUPPORTED_ARCHITECTURES:
                subimage_name = "__".join(subimage['digest'].split(':'))
                self.logger.debug("subimage_name: %s", subimage_name)

                subimage_arti_name = "{}/{}/{}/{}/manifest.json".format(
                    self.image_split[1],
                    self.image_split[2],
                    self.image_split[3],
                    subimage_name
                )
                tmp_curl2_output = self._arti_curl_get(subimage_arti_name)
                self.logger.debug("  tmp_curl2_output: %s", tmp_curl2_output)
                if tmp_curl2_output.returncode == 0:
                    # Succeeded in pulling the V2 type image manifest.
                    subimage_manifest = json.loads(tmp_curl2_output.stdout.decode())
                    # Copy the config
                    tmp_config_from_name = "{}/{}/{}/{}/{}".format(
                        self.image_split[1],
                        self.image_split[2],
                        self.image_split[3],
                        subimage_name,
                        "__".join(subimage_manifest['config']['digest'].split(':'))
                    )
                    tmp_config_to_name = "{}/{}/{}/{}/{}".format(
                        self.local_repo,
                        self.image_split[2],
                        self.image_split[3],
                        subimage_name,
                        "__".join(subimage_manifest['config']['digest'].split(':'))
                    )
                    tmp_curl3_output = self._arti_curl_copy(tmp_config_from_name, tmp_config_to_name)
                    self.logger.debug("tmp_curl3_output: %s", tmp_curl3_output)
                    if tmp_curl3_output.returncode != 0:
                        # Failed to copy the config
                        # FIXME: What error handling should happen here?
                        # FIXME: The '409: Conflict' error means the file has already been copied, likely from a
                        #        previous curation.
                        # FIXME: Still getting '409: Conflict' errors when the image hasn't already been copied.
                        #        Directories?
                        self.logger.debug("Successfully copied config")
                    # Copy the layer files
                    for tmp_sublayer in subimage_manifest['layers']:
                        tmp_sublayer_from_name = "{}/{}/{}/{}/{}".format(
                            self.image_split[1],
                            self.image_split[2],
                            self.image_split[3],
                            subimage_name, "__".join(tmp_sublayer['digest'].split(':'))
                        )
                        tmp_sublayer_to_name = "{}/{}/{}/{}/{}".format(
                            self.local_repo,
                            self.image_split[2],
                            self.image_split[3],
                            subimage_name, "__".join(tmp_sublayer['digest'].split(':'))
                        )
                        tmp_curl4_output = self._arti_curl_copy(tmp_sublayer_from_name, tmp_sublayer_to_name)
                        self.logger.debug("tmp_curl4_output: %s", tmp_curl4_output)
                        if tmp_curl4_output.returncode != 0:
                            # Failed to copy the config
                            # FIXME: What error handling should happen here?
                            # FIXME: The '409: Conflict' error means the file has already been copied, likely from a
                            #        previous curation.
                            # FIXME: Still getting '409: Conflict' errors when the image hasn't already been copied.
                            #        Directories?
                            self.logger.debug("Successfully copied layer")
                else:
                    # Failed to get manifest.json
                    # FIXME: What error handling should happen here?
                    pass
        self.logger.debug("Completed Copying V2 Images")

    def curate(self):
        self.logger.info("Curating the docker image: %s", self.docker_image)
        self._pull_image()
        self._pull_manifest()
        if self.docker_version == "V2":
            self._copy_v2()
        elif self.docker_version == "V1":
            self._copy_v1()
        self.logger.debug("Curating complete for docker image: %s", self.docker_image)

### MAIN ###
def main():
    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG
    )

    logging.info("Preparing Environment")
    tmp_payload_json = os.environ['res_curate_docker_payload']
    tmp_images = get_images_from_payload(tmp_payload_json)

    tmp_login_data = {}
    tmp_login_data['user'] = os.environ['int_artifactory_user']
    tmp_login_data['apikey'] = os.environ['int_artifactory_apikey']
    tmp_login_data['arti_url'] = os.environ['int_artifactory_url']
    tmp_login_data['local_repo'] = os.environ['local_repo_name']
    tmp_login_data['remote_repo'] = os.environ['remote_repo_name']
    tmp_login_data['docker_url'] = str(tmp_login_data['arti_url'].split('/')[2])

    docker_login(tmp_login_data)

    # NOTE: Currently, this script is expecting full docker image URLs, which
    #       include the hostname, (optional) repository name, group name, image
    #       name, and tag.  Example:
    #       example.jfrog.io/example-docker-remote/group/example:latest
    logging.info("Curating Images")
    tmp_dockerimage_pullers = []
    for tmp_img in tmp_images:
        tmp_dockerimage_pullers.append(DockerImagePuller(tmp_login_data, tmp_img))
    for tmp_puller in tmp_dockerimage_pullers:
        tmp_puller.curate()

    # Report Results
    # NOTE: This just prints the results to the log output.  This information
    #       can be gathered and pushed to a webhook on an external system for
    #       reporting, e.g. JIRA or ServiceNow.
    logging.info("Gathering Results")
    tmp_successes = []
    tmp_failures = []
    for tmp_puller in tmp_dockerimage_pullers:
        if tmp_puller.success:
            tmp_successes.append(tmp_puller.package_line)
        else:
            tmp_failures.append(tmp_puller.package_line)

    if len(tmp_successes) > 0:
        logging.info("Successfully Curated:")
        for item in tmp_successes:
            logging.info("  %s", item)
    if len(tmp_failures) > 0:
        logging.warning("Failed to Curate:")
        for item in tmp_failures:
            logging.warning("  %s", item)

if __name__ == "__main__":
    main()
