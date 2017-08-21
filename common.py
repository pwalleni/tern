'''
Common functions
'''

from utils import dockerfile as df
from utils import commands as cmds
from utils import cache as c

# constants strings
no_image_tag = '''No base image and/or tag listed in the command library \n
To add one, make an entry in command_lib/base.yml'''
no_command = '''No listing of hardcoded or retrieval steps for {image_tag} \n
To tell the tool this information make an entry in command_lib/base.yml'''
no_invocation = '''No invocation steps to perform within a container nor
on the host machine.\n To tell the tool how to retrieve this information,
make an entry in command_lib/base.yml'''
base_image_not_found = '''Failed to pull the base image. Perhaps it was
removed from Dockerhub'''

# dockerfile commands
docker_commands = []


def load_docker_commands(dockerfile):
    '''Given a dockerfile get a persistent list of docker commands'''
    global docker_commands
    # TODO: some checks on the passed argument would be nice here
    docker_commands = df.get_directive_list(df.get_command_list(dockerfile))


def check_base(base_image_tag):
    '''Given a base image tag check if an image exists
    If not then try to pull the image.'''
    image_tag_string = base_image_tag[0] + df.tag_separator + base_image_tag[1]
    success = cmds.check_image(image_tag_string)
    if not success:
        result = cmds.docker_command(cmds.pull, True, image_tag_string)
        if result is None:
            print(base_image_not_found)
            success = False
    return success


def get_base_dict(base_image_tag):
    '''Return the base dictionary from the command library'''
    image = base_image_tag[0]
    # check image
    listing = cmds.query_library(['base', image])
    if listing:
        if base_image_tag[1] == 'latest':
            tag = cmds.query_library(['base', image, 'latest'])
        else:
            tag = base_image_tag[1]
        # check tag
        listing = cmds.query_library(['base', image, tag])
    return listing


def get_base_packages(base_image_tag):
    '''Get the list of packages that are installed in the base layer using
    the invocations listed in the base command library
    If they don't exist inform the user'''
    # TODO: all of the commands listed so far are invoked within a container
    # there should be some mechanism where the commands get executed one
    # by one but also outside and inside the container
    image_tag_string = base_image_tag[0] + df.tag_separator + base_image_tag[1]
    base_dict = get_base_dict(base_image_tag)
    package_list = []
    if base_dict:
        names_dict = base_dict.get('names')
        if names_dict:
            package_list = cmds.invoke_in_container(
                names_dict['container']['invoke'], image_tag_string,
                base_dict['shell'])
        else:
            print(no_command.format(image_tag=image_tag_string))
    else:
        print(no_image_tag)
    return package_list


def get_base_layer_obj(dockerfile):
    '''Given a Dockerfile do the following:
        1. Get the base image and tag
        2. Find all the packages that are installed that are in the
        command library
        3. If there are any retrieval steps execute those
        4. Return a list of packages with the layer
        5. If there are none then return None'''
    base_image_tag = df.get_base_image_tag(
        df.get_base_instructions(docker_commands))
    if not check_base:
        print(base_image_not_found)
        raise
    else:
        # get the layers


    # for now the image that gets build will be tagged with an image name
    # and the name of the base image on which it is being built
    # The image name is in commands.py
    image_tag_string = cmds.image + df.tag_separator + base_image_tag[0]
    packages = cmds.get_packages(docker_commands)

    # for now remove all the packages that possibly got uninstalled
    packages['recognized'] = cmds.remove_uninstalled(packages['recognized'])
    packages['unrecognized'] = cmds.remove_uninstalled(
        packages['unrecognized'])
    # create a package dictionary to report
    report = {}
    report.update({'recognized': {'packages': []},
                   'unrecognized': {'packages': []}})
    # fill out recognized
    for command in packages['recognized'].keys():
        if cmds.check_all_pkgs(command):
            # in this case there is probably a url retrieval step
            # we can start a container here
            cmds.start_container(dockerfile, image_tag_string)
            # we can get the url retrieval step here
            pkg_rules = cmds.command_lib[command]['packages'][0]
            if 'url_retrieval' in pkg_rules.keys():
                for pkg in packages['recognized'][command]:
                    pkg_dict = {'name': pkg}
                    # TODO: allow for commands invoked on the host machine
                    if 'container' in pkg_rules['url_retrieval'].keys():
                        invoke = pkg_rules[
                            'url_retrieval']['container']['invoke']
                        results = cmds.invoke_in_container(
                            invoke, pkg, image_tag_string)
                        pkg_dict.update({'url': results})
                    report['recognized']['packages'].append(pkg_dict)
            cmds.remove_container()
            cmds.remove_image(image_tag_string)
    # fill out all the unrecognized packages
    report['unrecognized']['packages'] = packages['unrecognized']
    return report