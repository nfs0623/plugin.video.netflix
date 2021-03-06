# -*- coding: utf-8 -*-
"""Universal representation of VideoIds"""
from __future__ import unicode_literals

from functools import wraps

from .logging import debug


class InvalidVideoId(Exception):
    """The provided video id is not valid"""
    pass


class VideoId(object):
    """Universal representation of a video id. Video IDs can be of multiple
    types:
    - movie: a single identifier only for movieid, all other values must be
             None
    - show: a single identifier only for tvshowid, all other values must be
            None
    - season: identifiers for seasonid and tvshowid, all other values must
              be None
    - episode: identifiers for episodeid, seasonid and tvshowid, all other
               values must be None
    - unspecified: a single identifier only for videoid, all other values
                   must be None"""
    MOVIE = 'movie'
    SHOW = 'show'
    SEASON = 'season'
    EPISODE = 'episode'
    UNSPECIFIED = 'unspecified'
    TV_TYPES = [SHOW, SEASON, EPISODE]

    VALIDATION_MASKS = {
        0b10000: UNSPECIFIED,
        0b01000: MOVIE,
        0b00001: SHOW,
        0b00011: SEASON,
        0b00111: EPISODE
    }

    def __init__(self, **kwargs):
        self._id_values = _get_unicode_kwargs(kwargs)
        self._validate()

    def _validate(self):
        validation_mask = 0
        for index, value in enumerate(self._id_values):
            validation_mask |= (value is not None) << (4-index)
        try:
            self._mediatype = VideoId.VALIDATION_MASKS[validation_mask]
        except KeyError:
            raise InvalidVideoId

    @classmethod
    def from_path(cls, pathitems):
        """Create a VideoId instance from pathitems"""
        if pathitems[0] == VideoId.MOVIE:
            return cls(movieid=pathitems[1])
        elif pathitems[0] == VideoId.SHOW:
            return cls(tvshowid=_path_attr(pathitems, 1),
                       seasonid=_path_attr(pathitems, 3),
                       episodeid=_path_attr(pathitems, 5))
        return cls(videoid=pathitems[0])

    @classmethod
    def from_videolist_item(cls, video):
        """Create a VideoId from a video item contained in a
        videolist path response"""
        mediatype = video['summary']['type']
        video_id = video['summary']['id']
        if mediatype == VideoId.MOVIE:
            return cls(movieid=video_id)
        elif mediatype == VideoId.SHOW:
            return cls(tvshowid=video_id)
        else:
            raise InvalidVideoId(
                'Can only construct a VideoId from a show or movie item')

    @property
    def value(self):
        """The value of this VideoId"""
        return self._assigned_id_values()[0]

    @property
    def videoid(self):
        """The videoid value, if it exists"""
        return self._id_values[0]

    @property
    def movieid(self):
        """The movieid value, if it exists"""
        return self._id_values[1]

    @property
    def episodeid(self):
        """The episodeid value, if it exists"""
        return self._id_values[2]

    @property
    def seasonid(self):
        """The seasonid value, if it exists"""
        return self._id_values[3]

    @property
    def tvshowid(self):
        """The tvshowid value, if it exists"""
        return self._id_values[4]

    @property
    def mediatype(self):
        """The mediatype this VideoId instance represents.
        Either movie, show, season, episode or unspecified"""
        return self._mediatype

    def to_path(self):
        """Generate a valid pathitems list (['show', tvshowid, ...]) from
        this instance"""
        if self.videoid:
            return [self.videoid]
        if self.movieid:
            return [self.MOVIE, self.movieid]

        pathitems = [self.SHOW, self.tvshowid]
        if self.seasonid:
            pathitems.extend([self.SEASON, self.seasonid])
        if self.episodeid:
            pathitems.extend([self.EPISODE, self.episodeid])
        return pathitems

    def to_list(self):
        """Generate a list representation that can be used with get_path"""
        path = self._assigned_id_values()
        if len(path) > 1:
            path.reverse()
        return path

    def to_dict(self):
        """Return a dict containing the relevant properties of this
        instance"""
        result = {'mediatype': self.mediatype}
        result.update({prop: self.__getattribute__(prop)
                       for prop in ['videoid', 'movieid', 'tvshowid',
                                    'seasonid', 'episodeid']
                       if self.__getattribute__(prop) is not None})
        return result

    def derive_season(self, seasonid):
        """Return a new VideoId instance that represents the given season
        of this show. Raises InvalidVideoId is this instance does not
        represent a show."""
        if self.mediatype != VideoId.SHOW:
            raise InvalidVideoId('Cannot derive season VideoId from {}'
                                 .format(self))
        return type(self)(tvshowid=self.tvshowid, seasonid=unicode(seasonid))

    def derive_episode(self, episodeid):
        """Return a new VideoId instance that represents the given episode
        of this season. Raises InvalidVideoId is this instance does not
        represent a season."""
        if self.mediatype != VideoId.SEASON:
            raise InvalidVideoId('Cannot derive episode VideoId from {}'
                                 .format(self))
        return type(self)(tvshowid=self.tvshowid, seasonid=self.seasonid,
                          episodeid=unicode(episodeid))

    def derive_parent(self, depth):
        """Returns a new videoid for the parent mediatype (season for episodes,
        show for seasons) that is at the depth's level of the mediatype
        hierarchy or this instance if there is no parent mediatype."""
        if self.mediatype == VideoId.SEASON:
            return type(self)(tvshowid=self.tvshowid)
        if self.mediatype == VideoId.EPISODE:
            if depth == 0:
                return type(self)(tvshowid=self.tvshowid)
            if depth == 1:
                return type(self)(tvshowid=self.tvshowid,
                                  seasonid=self.seasonid)
        return self

    def _assigned_id_values(self):
        """Return a list of all id_values that are not None"""
        return [id_value
                for id_value in self._id_values
                if id_value is not None]

    def __str__(self):
        return '{}_{}'.format(self.mediatype, self.value)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        # pylint: disable=protected-access
        return self._id_values == other._id_values

    def __neq__(self, other):
        return not self.__eq__(other)


def _get_unicode_kwargs(kwargs):
    return tuple((unicode(kwargs[idpart])
                  if kwargs.get(idpart)
                  else None)
                 for idpart
                 in ['videoid', 'movieid', 'episodeid', 'seasonid',
                     'tvshowid'])


def _path_attr(pathitems, index):
    return pathitems[index] if len(pathitems) > index else None


def inject_video_id(path_offset, pathitems_arg='pathitems',
                    inject_remaining_pathitems=False):
    """Decorator that converts a pathitems argument into a VideoId
    and injects this into the decorated function instead. Pathitems
    that are to be converted into a video id must be passed into
    the function via kwarg defined by pathitems_arg (default=pathitems)"""
    # pylint: disable=missing-docstring
    def injecting_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                _path_to_videoid(kwargs, pathitems_arg, path_offset,
                                 inject_remaining_pathitems)
            except KeyError:
                raise Exception('Pathitems must be passed as kwarg {}'
                                .format(pathitems_arg))
            return func(*args, **kwargs)
        return wrapper
    return injecting_decorator


def _path_to_videoid(kwargs, pathitems_arg, path_offset,
                     inject_remaining_pathitems):
    """Parses a VideoId from the kwarg with name defined by pathitems_arg and
    adds it to the kwargs dict.
    If inject_remaining_pathitems is True, the pathitems representing the
    VideoId are stripped from the end of the pathitems and the remaining
    pathitems remain in kwargs. Otherwise, the pathitems will be removed
    from the kwargs dict."""
    kwargs['videoid'] = VideoId.from_path(kwargs[pathitems_arg][path_offset:])
    if inject_remaining_pathitems:
        kwargs[pathitems_arg] = kwargs[pathitems_arg][:path_offset]
    else:
        del kwargs[pathitems_arg]
