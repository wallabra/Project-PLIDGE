import ConfigParser
import struct_helper
import sys
import math
import random
import json
import subprocess

import map_sections

from omg.wad import *
from omg.mapedit import *


def percent_chance(percent):
    return random.random() * 100 < percent if percent > 0 else False


class NoMatchingSectionError(BaseException):
    pass


class OutputMap(object):
    def __init__(self, *section_pmsts):
        # type: (str) -> None
        self.available_sections = [map_sections.MapSectionType.load_from_pmst("pmst/" + pmst) for pmst in section_pmsts]

    def add_section_pmst(self, *section_pmsts):
        # type: (str) -> None
        self.available_sections += [map_sections.MapSectionType.load_from_pmst("pmst/" + pmst) for pmst in
                                    section_pmsts]

    def generate_random_map(self,
                            wad_filename,
                            map_name,
                            theme=None,
                            min_sections=10,
                            max_sections=18,
                            section_chance=(("hallway", 35), ("room", 60), ("outdoors", 15)),
                            texture_map={-1: "STARTAN1"},
                            flat_map={-1: "FLAT20"}
                            ):
        # type: (str, str, str, int, int, tuple) -> None
        """

        :rtype: None
        :param wad_filename: The filename of the WAD to save the map to.
        :param map_name: The name of the map to save.
        :param theme: The theme of the map.
        :param min_sections: The minimal number of sections to have in the map.
        :param max_sections: The maximum number of sections to have in the map.
        :param section_chance: Each type of sections used and their chances.
        """
        this_wad = WAD()

        try:
            this_wad.from_file("output/" + wad_filename + ".wad")

        except AssertionError:
            pass

        this_map = this_wad.maps[map_name] = MapEditor()

        try:
            current_section = random.choice(
                [section for section in self.available_sections if (
                    (section.theme == theme or not theme) and
                    (section.section_type in ("starting", "room")) and
                    not section.has_start_line
                )]
            )

        except IndexError:
            raise NoMatchingSectionError("There is no section of the kind specified to start the map!")

        this_map = add_section_to_map(current_section, this_map)
        sections_used = []

        assert min_sections > 0
        assert max_sections >= min_sections

        i = 1
        while i < random.randint(min_sections, max_sections):
            if not current_section:
                break

            chosen_index, chosen_end = random.choice(tuple(enumerate(current_section.end_lines)))

            current_section = None

            while current_section is None:
                for section_type, chance in section_chance:
                    try:
                        if percent_chance(chance):
                            possible_sections = [
                                section for section in self.available_sections if
                                (
                                    section.theme == theme or
                                    None in (section.theme, theme)
                                ) and (
                                    section.section_type == section_type or
                                    None in (section.section_type, section_type)
                                ) and (
                                    (
                                        len(sections_used) > 0 and
                                        sections_used[-1].end_widths[chosen_index] == section.start_width
                                    ) if section.has_start_line else True
                                ) and (
                                    len(sections_used) < 1 or section != sections_used[-1]
                                )
                            ]

                            print "Choosing the possible section in the list [{}]!".format(
                                 ", ".join(["{} vertexes and {} lines".format(
                                     len(section.wad_map.vertexes),
                                     len(section.wad_map.linedefs)
                                 ) for section in possible_sections])
                            )

                            print "Debug info: {}-{}:{}-{}:{}-{}".format(
                                section.theme,
                                theme,
                                section.section_type,
                                section_type,
                                sections_used[-1].end_widths[chosen_index] if len(sections_used) > 0 else "0",
                                section.start_width if section.has_start_line else "0"
                            )

                            print self.available_sections

                            if len(possible_sections) > 0:
                                current_section = random.choice(possible_sections)

                            else:
                                continue

                    except IndexError:
                        raise

            if current_section == None:
                break

            sections_used.append(current_section)

            assert isinstance(current_section, map_sections.MapSectionType)

            try:
                current_section.wad_map = align_sections(current_section, sections_used[-2], chosen_index)

            except IndexError:
                pass

            for index, textures in enumerate([(
                                                      sidedef.tx_mid,
                                                      sidedef.tx_up,
                                                      sidedef.tx_low
                                              ) for sidedef in current_section.wad_map.sidedefs]):
                for location, texture in enumerate(textures):
                    print "Replacing texture {} by {}!".format(
                        texture, texture_map[current_section.texture_map[texture]]
                    )
                    if location == 0:
                        current_section.wad_map.sidedefs[index].tx_mid = \
                            texture_map[current_section.texture_map[texture]]

                    elif location == 1:
                        current_section.wad_map.sidedefs[index].tx_up = \
                            texture_map[current_section.texture_map[texture]]

                    elif location == 2:
                        current_section.wad_map.sidedefs[index].tx_low = \
                            texture_map[current_section.texture_map[texture]]

                    else:
                        print "Warning: Texture map location index outside the range 0, 2! ({})".format(location)

            for index, flats in enumerate(
                    [(sector.tx_floor, sector.tx_ceil) for sector in current_section.wad_map.sectors]
            ):
                for location, flat in enumerate(flats):
                    print "Replacing flat {} by {}!".format(
                        flat, flat_map[current_section.flat_map[flat]]
                    )
                    if location == 0:
                        current_section.wad_map.sectors[index].tx_floor = flat_map[current_section.flat_map[flat]]

                    elif location == 1:
                        current_section.wad_map.sectors[index].tx_ceil = flat_map[current_section.flat_map[flat]]

                    else:
                        print "Warning: Flat map location index outside the range 0, 1! ({})".format(location)

            this_map = add_section_to_map(current_section, this_map)
            i += 1

        this_map.nodes = Lump("")
        this_map.blockmap = Lump("")
        this_map.reject = Lump("")
        this_wad.maps[map_name] = this_map.to_lumps()

        print "Outputting WAD to \'output/{}.wad\'!".format(wad_filename)
        this_wad.to_file("output/" + wad_filename + ".wad")

        subprocess.call("lib/ZenNode/ZenNode output/{}.wad".format(wad_filename))


def move_section(section, offset_x, offset_y):
    for vertex in section.vertexes:
        vertex.x += offset_x
        vertex.y += offset_y

    for thing in section.things:
        thing.x += offset_x
        thing.y += offset_y

    return section


def align_sections(section_a, section_b, index):
    # type: (map_sections.MapSectionType, map_sections.MapSectionType, int) -> MapSectionType


    """
    Aligns two sections so that their start and end lines align.

    :rtype: MapSectionType
    :param section_a: The section to align with section_b.
    :param section_b: The section with which section_a will be aligned.
    :param index: The index of the end line chosen for section_b.
    :return: The aligned version of section_b.
    """
    section_b.wad_map = move_section(
        section_a.wad_map,
        section_b.wad_map.vertexes[section_b.start_line.vx_a].x -
            section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].x,
        section_b.wad_map.vertexes[section_b.start_line.vx_a].y -
            section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].y,
    )

    print "\n\nRotation this section {} degrees clockwise.\n\n".format(map_sections.angle_between(
        (section_b.wad_map.vertexes[section_b.start_line.vx_a].x,
         section_b.wad_map.vertexes[section_b.start_line.vx_a].y),
        (section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].x,
         section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].y),
    ) - map_sections.angle_between(
        (section_b.wad_map.vertexes[section_b.start_line.vx_a].x,
         section_b.wad_map.vertexes[section_b.start_line.vx_a].y),
        (section_a.wad_map.vertexes[section_a.end_lines[index].vx_b].x,
         section_a.wad_map.vertexes[section_a.end_lines[index].vx_b].y),
    ))

    section_b.wad_map = rotate_map(
        section_b.wad_map,
        (
            map_sections.angle_between(
                (section_b.wad_map.vertexes[section_b.start_line.vx_a].x,
                 section_b.wad_map.vertexes[section_b.start_line.vx_a].y),
                (section_a.wad_map.vertexes[section_a.end_lines[index].vx_b].x,
                 section_a.wad_map.vertexes[section_a.end_lines[index].vx_b].y),
            ) -
            map_sections.angle_between(
                (section_b.wad_map.vertexes[section_b.start_line.vx_a].x,
                 section_b.wad_map.vertexes[section_b.start_line.vx_a].y),
                (section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].x,
                 section_a.wad_map.vertexes[section_a.end_lines[index].vx_a].y),
            )
        ),
        True
    )


def add_section_to_map(map_section, map_editor):
    # type: (map_sections.MapSectionType, MapEditor) -> MapEditor

    """
    Adds an map section to a map.

    :rtype: MapEditor
    :param map_section: The section to add to the map.
    :param map_editor: The map to add the section to.
    :returns: The map with the section in it.
    """

    map_editor.paste(map_section.wad_map)

    return map_editor


def rotate_map(map_editor, angle, clockwise=True, pivot=(0.0, 0.0)):
    # type: (MapEditor, float, bool, iter(float, float)) -> MapEditor

    """
    Rotates a map in the editor.

    :type map_editor: MapEditor
    :type angle: float
    :type clockwise: bool
    :type pivot: tuple(float, float)
    :rtype: MapEditor
    :param map_editor: The map editor to rotate.
    :param angle: The angle to rotate.
    :param clockwise: The direction of the turn. If True, clockwise, otherwise anti-clockwise.
    :param pivot: The pivot of rotation
    :return: Rotated version of the map.
    """

    angle_sine = math.sin(angle)
    angle_cosinee = math.cos(angle)

    if not angle:
        return map_editor

    if not clockwise:
        def rotation(asi, ac, x, y):
            # type: (float, float, int, int) -> tuple(float, float)
            return x * ac - y * asi, x * asi + y * ac

    else:
        def rotation(asi, ac, x, y):
            # type: (float, float, int, int) -> tuple(float, float)
            """

            :rtype: tuple(float, float)
            :param asi: 
            :param ac: 
            :param x: The X of the point to rotate.
            :param y: The Y of the point to rotate.
            :return: Rotated version of X, Y.
            """
            return x * ac + y * asi, -x * asi + y * ac

    for vertex in map_editor.vertexes:
        vertex.x -= pivot[0]
        vertex.y -= pivot[1]
        vertex.x, vertex.y = (int(a) for a in rotation(angle_sine, angle_cosinee, vertex.x, vertex.y))
        vertex.x += pivot[0]
        vertex.y += pivot[1]

    for thing in map_editor.things:
        thing.x -= pivot[0]
        thing.y -= pivot[1]
        thing.x, thing.y = (int(a) for a in rotation(angle_sine, angle_cosinee, thing.x, thing.y))
        thing.x += pivot[0]
        thing.y += pivot[1]

    return map_editor


def compile_pmst(json_to_parse, pmst_filename):
    instructions = json.load(open("rpmst/{}.json".format(json_to_parse)), "utf-8")

    print "Parsing RawPMST JSON: {}".format(instructions)

    wad_filename = instructions[u"wad"]
    map_name = instructions[u"map"]
    texture_map = instructions[u"texmap"]
    flat_map = instructions[u"flatmap"]
    start_line_numbers = instructions[u"start"]
    end_line_numbers = instructions[u"ends"]
    section_type = instructions[u"type"]
    theme = instructions[u"theme"]

    pmst_file = struct_helper.BinaryFile(pmst_filename, True)

    # Writing the WAD filename string
    pmst_file.write_binary_string(False, wad_filename)

    # Writing the map name string
    pmst_file.write_binary_string(False, map_name)

    # Writing the texture map
    pmst_file.write_binary(False, "I", len(texture_map))

    for texture, number in texture_map.items():
        pmst_file.write_binary_string(False, texture)
        pmst_file.write_binary(False, "i", number)

    # Writing the flat map
    pmst_file.write_binary(False, "I", len(flat_map))

    for flat, number in flat_map.items():
        pmst_file.write_binary_string(False, flat)
        pmst_file.write_binary(False, "i", number)

    # Writing the start and end lines
    pmst_file.write_binary(False, "i", start_line_numbers)
    pmst_file.write_binary(False, "H", len(end_line_numbers))

    for number in end_line_numbers:
        pmst_file.write_binary(False, "I", number)

    # Writing the ini_section type
    pmst_file.write_binary_string(False, section_type)

    # Writing the theme
    pmst_file.write_binary_string(False, theme)


if __name__ == "__main__":
    print "Debug mode activated!"

    config = ConfigParser.ConfigParser()
    config.read("config/{}.ini".format(sys.argv[1]))

    config.getlist = lambda ini_section, name: config.get(ini_section, name).split(config.get("General", "ListSep"))
    config.getdict = lambda ini_section, name: {
        key: item for key, item in [raw.split(config.get("General", "DictSep")) for raw in config.getlist(
        ini_section,
        name
    )]
        }

    sections = config.getlist("Generation", "Sections")
    output = config.get("Generation", "OutputWAD")
    map_name = config.get("Generation", "OutputMapName")
    theme = config.get("Generation", "Theme")
    min_sections = config.getint("Generation", "MinSections")
    max_sections = config.getint("Generation", "MaxSections")
    section_chance = tuple(((a, float(b)) for a, b in config.getdict("Generation", "SectionTypeChances").items()))
    flat_map = {int(chance): tex for chance, tex in config.getdict("Generation", "FlatMap").items()}
    texture_map = {int(chance): tex for chance, tex in config.getdict("Generation", "TexMap").items()}

    for rpmst in config.getlist("Compiling", "RawPMSTs"):
        try:
            compile_pmst(rpmst, "pmst/{}.pmst".format(rpmst))

        except IOError as error:
            print "Warning: Raw PMST \'rpmst/{}.json\' is missing! ({})".format(rpmst, error.strerror)

    map = OutputMap(*(str(section) + ".pmst" for section in sections))
    map.generate_random_map(
        output,
        map_name,
        theme,
        min_sections,
        max_sections,
        section_chance,
        texture_map,
        flat_map
    )
