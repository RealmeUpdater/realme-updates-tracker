#!/usr/bin/env python3.7
"""Realme Updates Tracker archive yaml generator"""
from glob import glob

import yaml


def main():
    """RealmeUpdatesTracker archiver"""
    with open("links.txt", 'r') as links_list:
        all_links = links_list.readlines()
    links = {line.split(' ')[0]: line.split(' ')[1].strip() for line in all_links}
    codenames = sorted(list(set(link.split('/')[-1].split('_')[0] for link in all_links)))
    for codename in codenames:
        roms = {version: link for version, link in links.items() if codename == link.split('/')[-1].split('_')[0]}
        with open(f'{codename}.yml', 'w') as output:
            yaml.dump({codename: roms}, output)

    yaml_files = [x for x in sorted(glob(f'*.yml'))
                  if not x.endswith('archive.yml')]
    yaml_data = []
    for file in yaml_files:
        with open(file, "r") as yaml_file:
            yaml_data.append(yaml.load(yaml_file, Loader=yaml.FullLoader))
    with open('archive.yml', "w") as output:
        yaml.dump(yaml_data, output, allow_unicode=True)


if __name__ == '__main__':
    main()
