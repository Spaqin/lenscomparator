from PIL import Image, ImageColor, ExifTags, ImageFont, ImageDraw
from os.path import abspath, isfile, isdir, splitext, basename
from os import listdir
import datetime
import enum
import argparse

class Config:
    # x, y in % of og image, marking the middle
    CENTER_POS = (.5, .5)  # center
    MID_POS = (.7, .3)  # upper right corner
    CORNER_POS = (.95, .05)  # upper right corner

    CropWidth = 400
    CropHeight = 300

    # one lens, all positions
    Merge = False

    # final picture settings
    Space = 10
    Headliner = 200
    Aperture_Space = 200

    Default_BG = (224, 224, 224)
    Other_BG = (200, 200, 200)

    Mark = False
    MarkOutline = (255, 0, 0)


class ImagePos(enum.Enum):
    CENTER = 0
    MID = 1
    CORNER = 2
    ALL = 255
    def get_coord(self):
        if self == self.CENTER:
            return Config.CENTER_POS
        elif self == self.MID:
            return Config.MID_POS
        elif self == self.CORNER:
            return Config.CORNER_POS

    def get_name(self):
        names = {
            self.CENTER: "Center",
            self.MID: "Mid",
            self.CORNER: "Corner"
        }
        return names[self]



class ImageMetadata:
    def __init__(self, name, focal_length, aperture):
        self.name = name
        self.focal_length = focal_length
        self.aperture = aperture


class ImageFragment:
    def __init__(self, image: Image.Image, metadata: ImageMetadata, pos: ImagePos):
        self.image = image
        self.metadata = metadata
        self.pos = pos

    @staticmethod
    def get_box(pos: ImagePos, img_w, img_h, crop_w, crop_h):
        pos_coord = pos.get_coord()
        center_w = img_w * pos_coord[0]
        center_h = img_h * pos_coord[1]
        # left, top, right, bottom lines
        box = (center_w - crop_w/2, center_h - crop_h/2, center_w + crop_w/2, center_h + crop_h/2)
        # adjusting in case it don't fit
        # adjusting left
        if box[0] < 0:
            box = (0, box[1], box[2]-box[0], box[3])
        # adjusting top
        if box[1] < 0:
            box = (box[0], 0, box[2], box[3] - box[1])
        # adjusting right
        if box[2] > img_w:
            box = (box[0] - (box[2] - img_w), box[1], img_w, box[3])
        # adjusting bottom
        if box[3] > img_h:
            box = (box[0], box[1] - (box[3] - img_h), box[2], img_h)

        return box

    @staticmethod
    def pull_fragment(complete_image: Image.Image, pos, width, height, metadata: ImageMetadata):
        box = ImageFragment.get_box(pos, complete_image.width, complete_image.height, width, height)
        img = complete_image.crop(box)
        return ImageFragment(img, metadata, pos)

class Comparison:
    def __init__(self):
        self.centers = []
        self.mids = []
        self.corners = []

    def generate_comparison_image(self, pos: ImagePos, space, headliner, aperture_space):
        if pos == ImagePos.CENTER:
            working_set = self.centers
        elif pos == ImagePos.MID:
            working_set = self.mids
        elif pos == ImagePos.CORNER:
            working_set = self.corners
        else:
            working_set = self.centers + self.mids + self.corners
        # get unique apertures, different models
        #space = Config.Space # space between images, both in x and y
        #headliner = Config.Headliner # space for lens name
        #aperture_space = 200 # space for aperture text
        apertures = dict()
        lens_names = set()
        max_w = 0
        max_h = 0
        for fragment in working_set:
            name = "{}\n{}mm:\n{}".format(fragment.metadata.name, fragment.metadata.focal_length, fragment.pos.get_name())
            if fragment.metadata.aperture not in apertures.keys():
                apertures[fragment.metadata.aperture] = {name: fragment}
            else:
                apertures[fragment.metadata.aperture][name] = fragment
            lens_names.add("{}{}".format(fragment.pos.value, name))
            max_h = max(max_h, fragment.image.height)
            max_w = max(max_w, fragment.image.width)
        img_h = (max_h+space) * len(apertures.keys()) + headliner
        img_w = (max_w+space) * len(lens_names) + aperture_space

        comparisonImg = Image.new('RGB', (img_w, img_h), Config.Default_BG)
        comparisonDraw = ImageDraw.Draw(comparisonImg)
        # make sure order isn't fucked up!!!!
        x_pos = 0
        y_pos = 0
        font = ImageFont.truetype("verdana.ttf", 16)
        font_ap = ImageFont.truetype("verdana.ttf", 24)
        x_pos += aperture_space + 15
        y_pos += headliner/3
        # sort lens_names so it's lens1 center, lens2 center, lens1 mid, lens2 mid, lens1 corn, lens2 corn...
        # clever solution that just pasted the value we wanted first in front, so sorting algo works easily...
        lens_names = sorted(lens_names)
        # amd just quietly rids of the addition.
        lens_names = [x[1:] for x in lens_names]

        for name in lens_names:
            # print columns (lens names)
            comparisonDraw.text((x_pos, y_pos), name, fill=(0, 0, 0), font=font)
            comparisonDraw.line((x_pos-15, 0, x_pos-15, headliner), fill=(0, 0, 0), width=5)
            x_pos += max_w
        # reset pos
        x_pos = 0
        y_pos = headliner
        i = 0
        for ap in sorted(apertures.keys()):
            # paste in results
            # alternate light grey and white backgrounds
            if i % 2:
                comparisonDraw.rectangle((0, y_pos, img_w, y_pos + max_h + space), fill=Config.Other_BG)
            i += 1
            # print aperture
            x_pos_ap = x_pos + aperture_space/3
            y_pos_ap = y_pos + max_h/2 - 8
            fmt = "F{:.1f}" if ap > 1 else "F{:.2f}"
            comparisonDraw.text((x_pos_ap, y_pos_ap), fmt.format(ap), fill=(0,0,0), font=font_ap)
            # paste images
            x_pos = aperture_space
            for name in lens_names:
                fragment = apertures[ap].get(name, None)
                if fragment:
                    comparisonImg.paste(fragment.image, (x_pos, y_pos))
                x_pos += max_w
            y_pos += max_h + space
            x_pos = 0

        return comparisonImg


    def add_fragment(self, fragment: ImageFragment):
        if fragment.pos == ImagePos.CENTER:
            self.centers.append(fragment)
        if fragment.pos == ImagePos.MID:
            self.mids.append(fragment)
        if fragment.pos == ImagePos.CORNER:
            self.corners.append(fragment)

def mark_image(img: Image):
    draw = ImageDraw.Draw(img)
    center_box = ImageFragment.get_box(ImagePos.CENTER, img.width, img.height, Config.CropWidth, Config.CropWidth)
    mid_box = ImageFragment.get_box(ImagePos.MID, img.width, img.height, Config.CropWidth, Config.CropWidth)
    corner_box = ImageFragment.get_box(ImagePos.CORNER, img.width, img.height, Config.CropWidth, Config.CropWidth)
    draw.rectangle(center_box, fill=None, outline=Config.MarkOutline, width=10)
    draw.rectangle(mid_box, fill=None, outline=Config.MarkOutline, width=10)
    draw.rectangle(corner_box, fill=None, outline=Config.MarkOutline, width=10)
    return img


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description="Lens comparator app.")
parser.add_argument("folders",
                    nargs="+",
                    type=str,
                    help="Required, folder with comparison files. If there is no EXIF data in JPEG files, please use following naming format:\n"
                    "LENSNAME_FOCALLENGTH_APERTURE.JPG, where lensname is anything and may include focal length e.g. for zooms. \n"
                    "Focal length includes actual focal length the shot was shot at.\n"
                    "Aperture however is either an integer, or a float with one dot.\n"
                    "e.g. Pergear35f1.6_33_2.8.jpg")
parser.add_argument("-m", "--merge",
                    action="store_true",
                    help="If present, will merge all lens comparison across different fields (useful if testing one lens)")
parser.add_argument("-cp", "--centerpos",
                    nargs=1,
                    type=str,
                    default=["50,50"],
                    help="Override of default center comparison location at 50, 50%% of the image.\n"
                         "Format: xpos,ypos e.g. 50,50")
parser.add_argument("-mp", "--midpos",
                    nargs=1,
                    type=str,
                    default=["70,30"],
                    help="Override of default mid comparison location at 70, 30%% (upper right) of the image.\n"
                         "Format: xpos,ypos e.g. 25,75")
parser.add_argument("-kp", "--cornerpos",
                    nargs=1,
                    type=str,
                    default=["100,0"],
                    help="Override of default mid comparison location at 100, 0%% (far right) of the image.\n"
                         "Format: xpos,ypos e.g. 5,95")
parser.add_argument("-cw", "--cropwidth",
                    nargs=1,
                    type=int,
                    default=[400],
                    help="Tested crop width in px. Default: 400")

parser.add_argument("-ch", "--cropheight",
                    nargs=1,
                    type=int,
                    default=[300],
                    help="Tested crop height in px. Default: 300")

parser.add_argument("-mk", "--mark",
                    action="store_true",
                    help="Mark one of the images with tested spots.")

# add scale? e.g. take a bigger crop but scale it down to fit?
# that's dumb and not very pixel-peepery

args = parser.parse_args()

def str_to_pos(s:str):
    xpos, ypos = s.split(",")
    xpos = float(xpos)/100
    ypos = float(ypos)/100
    return xpos,ypos

def exif_metadata(filepath):
    # experimental
    img = Image.open(filepath)
    exif = {
        ExifTags.TAGS[k]: v
        for k, v in img._getexif().items()
        if k in ExifTags.TAGS
    }
    focal_length = int(exif["FocalLength"][0]/100)
    aperture = float(exif["FNumber"][0]/100)
    name = exif["LensMake"].rstrip("\x00") + " " + exif["LensModel"].rstrip("\x00")
    return ImageMetadata(name, focal_length, aperture)

def metadata_from_file(filepath: str):
    splitted = basename(filepath).split("_")
    if len(splitted) < 3:
        return exif_metadata(filepath)
    else:
        return ImageMetadata(splitted[0], int(splitted[1]), float(splitted[2].rsplit(".", 1)[0]))



Config.Merge = args.merge
Config.CENTER_POS = str_to_pos(args.centerpos[0])
Config.MID_POS = str_to_pos(args.midpos[0])
Config.CORNER_POS = str_to_pos(args.cornerpos[0])

Config.CropWidth = args.cropwidth[0]
Config.CropHeight = args.cropheight[0]
Config.Mark = args.mark

for folder in args.folders:
    print("Folder: {}".format(folder))
    filenames = listdir(folder)
    files = ["{}\\{}".format(folder, x) for x in filenames]
    comp = Comparison()
    i = 1
    files = list(filter(lambda x: "Comparison_" not in x and ("jpg" in x or "JPG" in x) and "_marked" not in x, files)) # ignore nonjpegs, marked and comparisons
    for file in files:
        print("{} [{}/{}]".format(file, i, len(files)))
        meta = metadata_from_file(file)
        image = Image.open(file)
        comp.add_fragment(ImageFragment.pull_fragment(image, ImagePos.CENTER, Config.CropWidth, Config.CropHeight, meta))
        comp.add_fragment(ImageFragment.pull_fragment(image, ImagePos.MID, Config.CropWidth, Config.CropHeight, meta))
        comp.add_fragment(ImageFragment.pull_fragment(image, ImagePos.CORNER, Config.CropWidth, Config.CropHeight, meta))
        if i == 1 and Config.Mark:
            mark_image(image).save("{}_marked.JPG".format(file.rsplit(".", 1)[0]))
        i += 1

    if Config.Merge:
        img = comp.generate_comparison_image(ImagePos.ALL, Config.Space, Config.Headliner, Config.Aperture_Space)
        img.save("{}/Comparison_{}_all.JPG".format(folder, datetime.datetime.now().strftime("%Y-%m-%d_%H%M")), quality=100, subsampling=0)
    else:
        img = comp.generate_comparison_image(ImagePos.CENTER, Config.Space, Config.Headliner, Config.Aperture_Space)
        img.save("{}/Comparison_{}_center.JPG".format(folder, datetime.datetime.now().strftime("%Y-%m-%d_%H%M")), quality=100, subsampling=0)
        img = comp.generate_comparison_image(ImagePos.MID, Config.Space, Config.Headliner, Config.Aperture_Space)
        img.save("{}/Comparison_{}_mid.JPG".format(folder, datetime.datetime.now().strftime("%Y-%m-%d_%H%M")), quality=100, subsampling=0)
        img = comp.generate_comparison_image(ImagePos.CORNER, Config.Space, Config.Headliner, Config.Aperture_Space)
        img.save("{}/Comparison_{}_corner.JPG".format(folder, datetime.datetime.now().strftime("%Y-%m-%d_%H%M")), quality=100, subsampling=0)
