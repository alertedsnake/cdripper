#!/usr/bin/python
"""Simple CD ripper which also fetches cover images from Amazon.
Copyright (c) 2011 Michael Stella
"""

__author__ = 'Michael Stella'

import os, re, subprocess, sys, time, urllib
from optparse import OptionParser
from amazon.api import AmazonAPI
import CDDB, DiscID
import eyeD3
import xml.etree.cElementTree as etree

OUTPUT_PATH = '/home/michael/music'
RIPPER = 'cdparanoia'
ENCODER = {
    'mp3':      'lame -b 192 --nohist --id3v2-only',
    'flac':     'flac -5 --no-ogg',
    'ogg':      'oggenc -q 5',
}

AWS_ASSOCIATE_TAG="ripper"
AWS_ACCESS_KEY=""
AWS_SECRET_KEY=""
AWS_ENDPOINT="webservices.amazon.com"

def debug(s): pass

def main(opts, args):

    # read the disc and query FreeDB
    cd = DiscID.open()
    disc_id = DiscID.disc_id(cd)
    (qs, qi) = CDDB.query(disc_id)

    # 200 = one entry, 211 = multiple
    if qs != 200 and qs != 211:
        raise Exception("CDDB query failed: %d" % qs)

    # take just the first entry
    if type(qi) is list:
        qi = qi[0]

    (artist,album) = re.split('\s*/\s*', qi['title'])

    (rs, ri) = CDDB.read(qi['category'], qi['disc_id'])
    if rs != 210:
        raise Exception("CDDB read failed: %d" % qs)

    disc = {
        'artist':   artist,
        'album':    album,
        'year':     ri['DYEAR'],
        'tracks':   {},
        'cover':    None,
    }

    # read tracks
    for (key,value) in ri.items():
        if key.startswith('TTITLE'):
            num = int(key.lstrip('TTITLE')) + 1
            disc['tracks'][num] = value

    print "%s - %s (%d tracks)" % (disc['artist'], disc['album'], len(disc['tracks']))

    # setup the output directories
    outdir = os.path.join(opts.path, fixFileName(artist))
    if not os.path.exists(outdir):
        print("Making path %s" % outdir)
        os.mkdir(outdir)

    outdir = os.path.join(outdir, fixFileName(album))
    if not os.path.exists(outdir):
        print("Making path %s" % outdir)
        os.mkdir(outdir)

    # fetch cover image, if we can
    disc['cover'] = fetchCoverImage(outdir, artist, album)

    # Rippin' time
    ripTracks(opts, outdir, disc)


def ripTracks(opts, outdir, disc):

    trackCount = len(disc['tracks'])

    for num,title in disc['tracks'].items():
        tmpname = os.path.join(outdir, '{0:02d}.wav'.format(num))
        outname = os.path.join(outdir, '{track:02d}-{title}.{ext}'.format(track=num,
                                                     title=fixFileName(title),
                                                     ext=opts.type))
        print("Track {0:02d} - {1}".format(num, title))

        if not os.path.exists(outname):
            # rip
            if not os.path.exists(tmpname):
                ripper = "{0} {1} {2}".format(RIPPER, num, tmpname)
                debug("  running cmd: " + ripper)
                print("-------------------------------------------------------------------------")
                subprocess.call(ripper.split(' '))
                print("-------------------------------------------------------------------------")

            # encode
            encoder = "{0} {1} {2}".format(ENCODER[opts.type], tmpname, outname)
            debug("  running cmd: " + encoder)
            print("-------------------------------------------------------------------------")
            subprocess.call(encoder.split(' '))
            print("-------------------------------------------------------------------------")

            # remove the .wav
            if os.path.exists(tmpname):
                os.unlink(tmpname)

        # tag
        tag = eyeD3.Tag()
        tag.link(outname)

        tag.setArtist(disc['artist'])
        tag.setAlbum(disc['album'])
        tag.setDate(disc['year'])
        tag.setTitle(title)
        tag.setTrackNum((num, None))
        if disc['cover'] and len(tag.getImages()) == 0:
            tag.addImage(eyeD3.frames.ImageFrame.FRONT_COVER, disc['cover'])
        tag.update()


def fixFileName(fname):
    fname = re.sub('[&,.`\'$"]+','', fname)
    fname = fname.replace(' ', '_')
    fname = re.sub('__+','_',fname)

    return fname


def fetchCoverImage(outdir, artist, album):
    fn = os.path.join(outdir, 'cover.jpg')

    if os.path.exists(fn):
        return fn

    print("Fetching cover image")

    amazon = AmazonAPI(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_ASSOCIATE_TAG)

    # this is such a hack!
    def getFirst(ob):
        for i in ob:
            return i

    plist = amazon.search(SearchIndex='Music', Artist=artist, Keywords=album)
    entry = getFirst(plist)

    url = entry.medium_image_url

    if url is None:
        debug("Failed to find cover image!")
        return None

    img = urllib.urlopen(url)
    with open(fn , 'w') as f:
        f.write(img.read())

    return fn



def init():
    global debug

    parser = OptionParser()

    parser.add_option('--path', type="string", default=OUTPUT_PATH, help="output path")
    parser.add_option('--type', type="string", default="mp3", help="output format")
    parser.add_option('--debug', action="store_true", default=False, help="verbose output")


    (opts,args) = parser.parse_args()

    if opts.debug:
        def debug(s):
            print s

    return (opts,args)


if __name__ == "__main__":
    try:
        main(*init())
    except KeyboardInterrupt:
        sys.exit(1)
