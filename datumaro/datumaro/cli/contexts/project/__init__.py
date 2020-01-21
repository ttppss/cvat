
# Copyright (C) 2019 Intel Corporation
#
# SPDX-License-Identifier: MIT

import argparse
from enum import Enum
import logging as log
import os
import os.path as osp
import shutil

from datumaro.components.project import Project
from datumaro.components.comparator import Comparator
from datumaro.components.dataset_filter import DatasetItemEncoder
from .diff import DiffVisualizer
from ...util import add_subparser, CliException, MultilineFormatter
from ...util.project import make_project_path, load_project, \
    generate_next_dir_name


def build_create_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(help="Create empty project",
        description="""
            Create a new empty project.|n
            |n
            Examples:|n
            - Create a project in the current directory:|n
            |s|screate -n myproject|n
            |n
            - Create a project in other directory:|n
            |s|screate -o path/I/like/
        """,
        formatter_class=MultilineFormatter)

    parser.add_argument('-o', '--output-dir', default='.', dest='dst_dir',
        help="Save directory for the new project (default: current dir")
    parser.add_argument('-n', '--name', default=None,
        help="Name of the new project (default: same as project dir)")
    parser.add_argument('--overwrite', action='store_true',
        help="Overwrite existing files in the save directory")
    parser.set_defaults(command=create_command)

    return parser

def create_command(args):
    project_dir = osp.abspath(args.dst_dir)
    project_path = make_project_path(project_dir)

    if osp.isdir(project_dir) and os.listdir(project_dir):
        if not args.overwrite:
            raise CliException("Directory '%s' already exists "
                "(pass --overwrite to force creation)" % project_dir)
        else:
            shutil.rmtree(project_dir)
    os.makedirs(project_dir, exist_ok=args.overwrite)

    if not args.overwrite and osp.isfile(project_path):
        raise CliException("Project file '%s' already exists "
            "(pass --overwrite to force creation)" % project_path)

    project_name = args.name
    if project_name is None:
        project_name = osp.basename(project_dir)

    log.info("Creating project at '%s'" % project_dir)

    Project.generate(project_dir, {
        'project_name': project_name,
    })

    log.info("Project has been created at '%s'" % project_dir)

    return 0

def build_import_parser(parser_ctor=argparse.ArgumentParser):
    import datumaro.components.importers as importers_module
    builtin_importers = [name for name, cls in importers_module.items]

    parser = parser_ctor(help="Create project from existing dataset",
        description="""
            Creates a project from an existing dataset. The source can be:|n
            - a dataset in a supported format (check 'formats' section below)|n
            - a Datumaro project|n
            |n
            Formats:|n
            Datasets come in a wide variety of formats. Each dataset
            format defines its own data structure and rules on how to
            interpret the data. For example, the following data structure
            is used in COCO format:|n
            /dataset/|n
            - /images/<id>.jpg|n
            - /annotations/|n
            |n
            In Datumaro dataset formats are supported by
            Extractor-s and Importer-s.
            An Extractor produces a list of dataset items corresponding
            to the dataset. An Importer creates a project from the
            data source location.
            It is possible to add a custom Extractor and Importer.
            To do this, you need to put an Extractor and
            Importer implementation scripts to
            <project_dir>/.datumaro/extractors
            and <project_dir>/.datumaro/importers.|n
            |n
            List of supported dataset formats: %s|n
            |n
            Examples:|n
            - Create a project from VOC dataset in the current directory:|n
            |s|simport -f voc -i path/to/voc|n
            |n
            - Create a project from COCO dataset in other directory:|n
            |s|simport -f coco -i path/to/coco -o path/I/like/
        """ % ', '.join(builtin_importers),
        formatter_class=MultilineFormatter)

    parser.add_argument('-o', '--output-dir', default='.', dest='dst_dir',
        help="Directory to save the new project to (default: current dir)")
    parser.add_argument('-n', '--name', default=None,
        help="Name of the new project (default: same as project dir)")
    parser.add_argument('--copy', action='store_true',
        help="Copy the dataset instead of saving source links")
    parser.add_argument('--skip-check', action='store_true',
        help="Skip source checking")
    parser.add_argument('--overwrite', action='store_true',
        help="Overwrite existing files in the save directory")
    parser.add_argument('-i', '--input-path', required=True, dest='source',
        help="Path to import project from")
    parser.add_argument('-f', '--format', required=True,
        help="Source project format")
    # parser.add_argument('extra_args', nargs=argparse.REMAINDER,
    #     help="Additional arguments for importer (pass '-- -h' for help)")
    parser.set_defaults(command=import_command)

    return parser

def import_command(args):
    project_dir = osp.abspath(args.dst_dir)
    project_path = make_project_path(project_dir)

    if osp.isdir(project_dir) and os.listdir(project_dir):
        if not args.overwrite:
            raise CliException("Directory '%s' already exists "
                "(pass --overwrite to force creation)" % project_dir)
        else:
            shutil.rmtree(project_dir)
    os.makedirs(project_dir, exist_ok=args.overwrite)

    if not args.overwrite and osp.isfile(project_path):
        raise CliException("Project file '%s' already exists "
            "(pass --overwrite to force creation)" % project_path)

    project_name = args.name
    if project_name is None:
        project_name = osp.basename(project_dir)

    log.info("Importing project from '%s' as '%s'" % \
        (args.source, args.format))

    source = osp.abspath(args.source)
    project = Project.import_from(source, args.format)
    project.config.project_name = project_name
    project.config.project_dir = project_dir

    if not args.skip_check or args.copy:
        log.info("Checking the dataset...")
        dataset = project.make_dataset()
    if args.copy:
        log.info("Cloning data...")
        dataset.save(merge=True, save_images=True)
    else:
        project.save()

    log.info("Project has been created at '%s'" % project_dir)

    return 0


class FilterModes(Enum):
    # primary
    items = 1
    annotations = 2
    items_annotations = 3

    # shortcuts
    i = 1
    a = 2
    i_a = 3

    @staticmethod
    def parse(s):
        s = s.lower()
        s = s.replace('+', '_')
        return FilterModes[s]

    @classmethod
    def make_filter_args(cls, mode):
        if mode == cls.items:
            return {}
        elif mode == cls.annotations:
            return {
                'filter_annotations': True
            }
        elif mode == cls.items_annotations:
            return {
                'filter_annotations': True,
                'remove_empty': True,
            }
        else:
            raise NotImplementedError()

    @classmethod
    def list_options(cls):
        return [m.name.replace('_', '+') for m in cls]

def build_export_parser(parser_ctor=argparse.ArgumentParser):
    import datumaro.components.converters as converters_module
    builtin_converters = [name for name, cls in converters_module.items]

    parser = parser_ctor(help="Export project",
        description="""
            Exports the project dataset in some format. Optionally, a filter
            can be passed, check 'extract' command description for
            explanations on this.|n
            |n
            Formats:|n
            In Datumaro dataset formats are supported by Converter-s.
            A Converter produces a dataset of a specific format
            from dataset items. It is possible to add a custom Converter.
            To do this, you need to put a Converter
            definition script to <project_dir>/.datumaro/converters.|n
            |n
            List of supported dataset formats: %s|n
            |n
            Examples:|n
            - Export project as a VOC-like dataset:|n
            |s|sexport -f voc|n
            |n
            - Export project as a COCO-like dataset in other directory:|n
            |s|sexport -f coco -o path/I/like/
        """ % ', '.join(builtin_converters),
        formatter_class=MultilineFormatter)

    parser.add_argument('-e', '--filter', default=None,
        help="Filter expression for dataset items")
    parser.add_argument('--filter-mode', default=FilterModes.i.name,
        type=FilterModes.parse,
        help="Filter mode (options: %s; default: %s)" % \
            (', '.join(FilterModes.list_options()) , '%(default)s'))
    parser.add_argument('-o', '--output-dir', dest='dst_dir', default=None,
        help="Directory to save output (default: a subdir in the current one)")
    parser.add_argument('--overwrite', action='store_true',
        help="Overwrite existing files in the save directory")
    parser.add_argument('-p', '--project', dest='project_dir', default='.',
        help="Directory of the project to operate on (default: current dir)")
    parser.add_argument('-f', '--format', required=True,
        help="Output format")
    parser.add_argument('extra_args', nargs=argparse.REMAINDER, default=None,
        help="Additional arguments for converter (pass '-- -h' for help)")
    parser.set_defaults(command=export_command)

    return parser

def export_command(args):
    project = load_project(args.project_dir)

    dst_dir = args.dst_dir
    if dst_dir:
        if not args.overwrite and osp.isdir(dst_dir) and os.listdir(dst_dir):
            raise CliException("Directory '%s' already exists "
                "(pass --overwrite to force creation)" % dst_dir)
    else:
        dst_dir = generate_next_dir_name('%s-export-%s' % \
            (project.config.project_name, args.format))
    dst_dir = osp.abspath(dst_dir)

    try:
        converter = project.env.make_converter(args.format,
            cmdline_args=args.extra_args)
    except KeyError:
        raise CliException("Converter for format '%s' is not found" % \
            args.format)

    filter_args = FilterModes.make_filter_args(args.filter_mode)

    log.info("Loading the project...")
    dataset = project.make_dataset()

    log.info("Exporting the project...")
    dataset.export_project(
        save_dir=dst_dir,
        converter=converter,
        filter_expr=args.filter,
        **filter_args)
    log.info("Project exported to '%s' as '%s'" % \
        (dst_dir, args.format))

    return 0

def build_extract_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(help="Extract subproject",
        description="""
            Extracts a subproject that contains only items matching filter.
            A filter is an XPath expression, which is applied to XML
            representation of a dataset item. Check '--dry-run' parameter
            to see XML representations of the dataset items.|n
            |n
            To filter annotations use '-m' parameter.
            When filtering annotations, use 'items+annotations'
            mode to point that annotation-less dataset items should be
            removed. To select an annotation, write an XPath that
            returns 'annotation' elements (see examples).|n
            |n
            Examples:|n
            - Filter images with width < height:|n
            |s|sextract -e '/item[image/width < image/height]'|n
            |n
            - Filter images with large-area bboxes:|n
            |s|sextract -e '/item[annotation/type=\"bbox\" and
                annotation/area>2000]'|n
            |n
            - Filter out all irrelevant annotations from items:|n
            |s|sextract -m a -e '/item/annotation[label = \"person\"]'|n
            |n
            - Filter occluded annotations and items, if no annotations left:|n
            |s|sextract -m i+a -e '/item/annotation[occluded="True"]'
        """,
        formatter_class=MultilineFormatter)

    parser.add_argument('-e', '--filter', default=None,
        help="XML XPath filter expression for dataset items")
    parser.add_argument('-m', '--mode', default=FilterModes.i.name,
        type=FilterModes.parse,
        help="Filter mode (options: %s; default: %s)" % \
            (', '.join(FilterModes.list_options()) , '%(default)s'))
    parser.add_argument('--dry-run', action='store_true',
        help="Print XML representations to be filtered and exit")
    parser.add_argument('-o', '--output-dir', dest='dst_dir', default=None,
        help="Output directory (default: update current project)")
    parser.add_argument('-p', '--project', dest='project_dir', default='.',
        help="Directory of the project to operate on (default: current dir)")
    parser.set_defaults(command=extract_command)

    return parser

def extract_command(args):
    project = load_project(args.project_dir)

    if not args.dst_dir:
        dst_dir = generate_next_dir_name('%s-filter' % \
            project.config.project_name)
    dst_dir = osp.abspath(dst_dir)

    dataset = project.make_dataset()

    filter_args = FilterModes.make_filter_args(args.filter_mode)

    if args.dry_run:
        dataset = dataset.extract(filter_expr=args.filter,
            filter_annotations=args.filter_annotations, **kwargs)
        for item in dataset:
            encoded_item = DatasetItemEncoder.encode(item, dataset.categories())
            xml_item = DatasetItemEncoder.to_string(encoded_item)
            print(xml_item)
        return 0

    if not args.filter:
        raise CliException("Expected a filter expression ('-e' argument)")

    os.makedirs(dst_dir, exist_ok=False)
    dataset.extract_project(save_dir=dst_dir, filter_expr=args.filter,
        **filter_args)

    log.info("Subproject has been extracted to '%s'" % dst_dir)

    return 0

def build_merge_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(help="Merge projects",
        description="""
            Updates items of the current project with items
            from the other project.|n
            |n
            Examples:|n
            - Update a project with items from other project:|n
            |s|smerge -p path/to/first/project path/to/other/project
        """,
        formatter_class=MultilineFormatter)

    parser.add_argument('other_project_dir',
        help="Directory of the project to get data updates from")
    parser.add_argument('-o', '--output-dir', dest='dst_dir', default=None,
        help="Output directory (default: current project's dir)")
    parser.add_argument('-p', '--project', dest='project_dir', default='.',
        help="Directory of the project to operate on (default: current dir)")
    parser.set_defaults(command=merge_command)

    return parser

def merge_command(args):
    first_project = load_project(args.project_dir)
    second_project = load_project(args.other_project_dir)

    first_dataset = first_project.make_dataset()
    first_dataset.update(second_project.make_dataset())

    dst_dir = args.dst_dir
    first_dataset.save(save_dir=dst_dir)

    if dst_dir is None:
        dst_dir = first_project.config.project_dir
    dst_dir = osp.abspath(dst_dir)
    log.info("Merge results have been saved to '%s'" % dst_dir)

    return 0

def build_diff_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(help="Compare projects",
        description="""
        Compares two projects.|n
        |n
        Examples:|n
        - Compare two projects, consider bboxes matching if their IoU > 0.7,|n
        |s|s|s|sprint results to Tensorboard:
        |s|sdiff path/to/other/project -o diff/ -f tensorboard --iou-thresh 0.7
        """,
        formatter_class=MultilineFormatter)

    parser.add_argument('other_project_dir',
        help="Directory of the second project to be compared")
    parser.add_argument('-o', '--output-dir', dest='dst_dir', default=None,
        help="Directory to save comparison results (default: do not save)")
    parser.add_argument('-f', '--format',
        default=DiffVisualizer.DEFAULT_FORMAT,
        choices=[f.name for f in DiffVisualizer.Format],
        help="Output format (default: %(default)s)")
    parser.add_argument('--iou-thresh', default=0.5, type=float,
        help="IoU match threshold for detections (default: %(default)s)")
    parser.add_argument('--conf-thresh', default=0.5, type=float,
        help="Confidence threshold for detections (default: %(default)s)")
    parser.add_argument('-p', '--project', dest='project_dir', default='.',
        help="Directory of the first project to be compared (default: current dir)")
    parser.set_defaults(command=diff_command)

    return parser

def diff_command(args):
    first_project = load_project(args.project_dir)
    second_project = load_project(args.other_project_dir)

    comparator = Comparator(
        iou_threshold=args.iou_thresh,
        conf_threshold=args.conf_thresh)

    save_dir = args.dst_dir
    if not save_dir:
        save_dir = generate_next_dir_name('%s-%s-diff' % (
            first_project.config.project_name,
            second_project.config.project_name)
        )
    save_dir = osp.abspath(save_dir)
    if save_dir is not None:
        log.info("Saving diff to '%s'" % save_dir)

    visualizer = DiffVisualizer(save_dir=save_dir, comparator=comparator,
        output_format=args.format)
    visualizer.save_dataset_diff(
        first_project.make_dataset(),
        second_project.make_dataset())

    return 0

def build_transform_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(help="Transform project",
        description="""
            Applies some operation to dataset items in the project
            and produces a new project.
        """,
        formatter_class=MultilineFormatter)

    parser.add_argument('-t', '--transform', required=True,
        help="Transform to apply to the project")
    parser.add_argument('-o', '--output-dir', dest='dst_dir', default=None,
        help="Directory to save output (default: current dir)")
    parser.add_argument('-p', '--project', dest='project_dir', default='.',
        help="Directory of the project to operate on (default: current dir)")
    parser.set_defaults(command=transform_command)

    return parser

def transform_command(args):
    project = load_project(args.project_dir)

    dst_dir = osp.abspath(args.dst_dir)
    if dst_dir is not None:
        os.makedirs(dst_dir, exist_ok=False)

    project.make_dataset().transform_project(
        method=args.transform,
        save_dir=dst_dir
    )

    log.info("Transform results saved to '%s'" % (dst_dir))

    return 0


def build_parser(parser_ctor=argparse.ArgumentParser):
    parser = parser_ctor(
        description="""
            Manipulate projects.|n
            |n
            By default, the project to be operated on is searched for
            in the current directory. An additional '-p' argument can be
            passed to specify project location.
        """,
        formatter_class=MultilineFormatter)

    subparsers = parser.add_subparsers()
    add_subparser(subparsers, 'create', build_create_parser)
    add_subparser(subparsers, 'import', build_import_parser)
    add_subparser(subparsers, 'export', build_export_parser)
    add_subparser(subparsers, 'extract', build_extract_parser)
    add_subparser(subparsers, 'merge', build_merge_parser)
    add_subparser(subparsers, 'diff', build_diff_parser)
    add_subparser(subparsers, 'transform', build_transform_parser)

    return parser