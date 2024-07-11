# %% imports
from itertools import islice, chain


# %% define class
class Dec:
    """Represents either
        - a time span (a duration without a specific start or end),
        - a time point (a specific instant in time),
        - a time period (the duration in between two specific points in time),
        - a series of time spans, time points, or time periods.

        To create time spans, pass year and/or day values to the Dec class.

        Span instantiation examples:
        >>> one_year = Dec(1)
        >>> one_year
        Dec(day=365)
        >>> one_day = Dec(0, 1)
        >>> one_day
        Dec(day=1)
        >>> one_beat = Dec(0, 1e-5)
        >>> one_beat
        Dec(day=0.00001)

        To create a time point, pass a time zone to the Dec class.

        Time point instantiation examples:
        >>> dec_epoch = Dec(0, 0, 0)
        >>> dec_epoch
        Dec(zone=0)
        >>> unix_epoch = Dec(1969, 306, 0)
        >>> unix_epoch
        Dec(year=1969, date=306, zone=0)
        >>> year2K = Dec(2000, 0, 0)
        >>> year2K
        Dec(year=2000, zone=0)
        >>> dayB4year2K = Dec(2000, -1, 0)
        >>> dayB4year2K
        Dec(year=1999, date=365, zone=0)

        To create a period, pass
        - a time point to a time span or a time point.
        - an int, float, or time span to a time point.
        Time point arguments are interpreted as time period stopping points.
        Other argument types are interpreted as time period durations.

        Period creation examples:
        >>> first_decade = Dec(0, 0, 0)(Dec(10))
        >>> first_decade
        Dec(zone=0, stop=[Dec(day=3652)])
        >>> second_decade = Dec(10)(Dec(20, 0, 0))
        >>> second_decade
        Dec(day=3652, stop=[Dec(year=20, zone=0)])
        >>> third_decade = Dec(20, 0, 0)(3652)
        >>> third_decade
        Dec(year=20, zone=0, stop=[3652])

        To create a series instead of a period, pass more than one argument.

        Time series creation examples:
        >>> first_five_noons = Dec(day=.5, zone=0)(5, 1)
        >>> first_five_noons
        Dec(time=5, zone=0, stop=[5], step=[(1)])
        >>> list(first_five_noons)
        [0.5, 1.5, 2.5, 3.5, 4.5]

        You can do arithmetic with any Dec object.

        Arithmetic examples:
        >>> one_year + one_beat
        Dec(day=365.00001)
        >>> one_year - one_beat
        Dec(day=364.99999)
        >>> dec_epoch + one_year
        Dec(year=1, zone=0)

        Args:
        year: a common year with 365 days or a leap year with 366 days.
        day: the base unit for Dec timekeeping.
        zone: the Dec time zone, 0 to 9 decidays (tenths of a day).
        utc: the UTC time zone offset in hours, a non-Dec unit used only for conversion
        degree: the degrees of longitude, 1 deciday is 36 degrees.
        month: 28, 29, 30, or 31 days, a non-Dec unit, used only for conversion
        dotm: the day of the month, a non-Dec unit, used only for conversion
        week: 7 days, a non-Dec unit, used only for conversion
        dotw: the day of the week, a non-Dec unit, used only for conversion
        hour: 1/24 of a day, a non-Dec unit, used only for conversion
        minute: 1/1440 of a day, a non-Dec unit, used only for conversion
        second: 1/86400 of a day, a non-Dec unit, used only for conversion
        millisecond: 1/86400000 of a day, a non-Dec unit, used only for conversion

    Returns:
        This is a description of what is returned.

    """

    def __init__(
        self,
        year=0.0,
        day=0.0,
        zone=None,
        utc=None,
        degree=None,
        month=3,
        dotm=1,
        week=0,
        dotw=3,
        hour=0,
        minute=0,
        second=0,
        millisecond=0,
    ):
        self.zone = int(((zone if zone else 0)
            + ((utc * 15 if utc else 0) + (((
                degree + 360 if (degree := degree % 360) < 0 else degree
        ) + 18) if degree else 0)) / 36 % 10) // 1) if any(
            i is not None for i in [zone, utc, degree]) else None
        self.dote = (
            self.year2dote(year) + day
            + (153 * (month - 3 if month > 2 else month + 9) + 2) // 5
            + dotm - 1 + week * 7 + dotw - 3
            - (self.zone / 10 if self.zone is not None else 0)
            + (hour + minute / 60 + second / 3600 + millisecond / 3600000) / 24
        )
        self._save_year_and_date()
        self._stops = []
        self._steps = []
        self._calls = []
        self._range = iter([self.dote])

    @staticmethod
    def dote2date(dote):
        cykl = (dote if dote >= 0 else dote - 146096) // 146097
        dotc = dote - cykl * 146097
        yotc = (dotc - dotc // 1460 + dotc // 36524 - dotc // 146096) / 365
        date = int(dotc) + (yotc := int(yotc)) // 100 - yotc * 365 - yotc // 4
        return [yotc + cykl * 400, date]

    @staticmethod
    def year2dote(year):
        cykl = (year if year >= 0 else year - 399) // 400
        yotc = year - cykl * 400
        return cykl * 146097 + yotc * 365 + yotc // 4 - yotc // 100

    def _save_year_and_date(self):
        cykl = (
            self._dote if self.dote >= 0 else self._dote - 146096
        ) // 146097
        dotc = self._dote - cykl * 146097
        yotc = (dotc - dotc // 1460 + dotc // 36524 - dotc // 146096) / 365
        self._year = yotc + cykl * 400
        self._date = (
            int(dotc) + (yotc := int(yotc)) // 100 - yotc * 365 - yotc // 4
        )

    def __call__(self, stop=None, *steps):
        if stop is not None:
            self._stops += [stop]
            self._steps += [steps]
            self._calls += [(stop, *steps)]
            self._create_range()
        return self

    def _create_range(self):
        starts = (self.dote,)
        nsteps = len(self._steps)
        for i, stop in enumerate(self._stops):
            starts = self._generate(
                starts, stop, self._steps[i] if i + 1 <= nsteps else ()
            )
        self._range = iter(starts)

    def __getitem__(self, key):
        self._create_range()
        if type(key) == slice and all(
            s is None or s >= 0 for s in (key.start, key.stop, key.step)
        ):
            return islice(self._range, key.start, key.stop, key.step)
        elif type(key) == int and key >= 0:
            return next(islice(self._range, key, None))
        elif type(key) == slice or type(key) == int:
            return tuple(self._range)[key]
        key = self._flatten(key)
        if all(i >= 0 for i in key):
            return chain(islice(self._range, i, None) for i in key)
        else:
            t = tuple(self._range)
            return tuple(t[i] for i in key)

    @property
    def leap(self):
        y = self.year // 1 + 1
        return y % 4 == 0 and y % 100 != 0 or y % 400 == 0

    @property
    def dote(self):
        return self._dote

    @dote.setter
    def dote(self, value):
        self._dote = value
        self._save_year_and_date()

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value):
        self._dote = self.year2dote(value)
        self._save_year_and_date()

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        diff = value - self._date
        self._dote += diff
        self._save_year_and_date()

    def __str__(self):
        dote = self.dote + (self.zone / 10 if self.zone is not None else 0)
        if self.zone is None:
            # Duration in days with optional iteration logic
            return (
                format(dote, '.5f').rstrip('0').rstrip('.')
                + "".join(map(str, self._calls))
            )
        else:
            year, date = self.dote2date(dote)
            # Instant (year+deciday-zone) with optional iteration logic
            return (
                f"{int(year):04}+{date:03}"
                + format(dote % 1 * 10, '.4f').rstrip('0').rstrip('.')
                + f"-{self.zone}"
                + "".join(map(str, self._calls))
            )

    def __repr__(self):
        if self.zone is None:
            pre = "Dec(" + (
                f"day={format(dote, '.5f').rstrip('0').rstrip('.')}"
                if (dote := self.dote + (
                    self.zone / 10 if self.zone is not None else 0)) else ""
            )
        else:
            year, date = self.dote2date(dote := self.dote
                + (self.zone / 10 if self.zone is not None else 0)
            )
            pre = "Dec(" + ", ".join(filter(None, [
                f"year={int(year)}" if year else "",
                f"date={int(date)}" if date else "",
                f"time={time:.4g}" if (time := dote % 1 * 10) else "",
                f"zone={int(self.zone)}"
            ]))
        return (
            ", ".join(filter(None, [
                pre, f"stop={str(self._stops)}" if self._stops else "",
                f"step={str(self._steps)}".replace(',)', ')').replace(
                    '),(', ')(') if any(self._steps) else ""
                ])) + ")"
        )

    def __int__(self):
        return int(self.dote)

    def __float__(self):
        return float(self.dote)

    def __bool__(self):
        return bool(self.dote)

    def __invert__(self):
        return ~self.dote

    def __pos__(self):
        return +self.dote

    def __neg__(self):
        return -self.dote

    def __round__(self):
        return round(self.dote)

    def __floor__(self):
        return self.dote // 1

    def __trunc__(self):
        return self.dote.__trunc__()

    def __abs__(self):
        return abs(self.dote)

    def __ceil__(self):
        return self.dote.__ceil__()

    def __eq__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote == other.dote)
        return self.dote == other

    def __ne__(self, other):
        if isinstance(other, Dec):
            return self.dote != other.dote
        return self.dote != other

    def __gt__(self, other):
        # if comparing against a string try to parse string to dote
        if isinstance(other, Dec):
            return self.dote > other.dote
        return self.dote > other

    def __lt__(self, other):
        if isinstance(other, Dec):
            return self.dote < other.dote
        return self.dote < other

    def __ge__(self, other):
        if isinstance(other, Dec):
            return self.dote >= other.dote
        return self.dote >= other

    def __le__(self, other):
        if isinstance(other, Dec):
            return self.dote <= other.dote
        return self.dote <= other

    def __add__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote + other.dote)
        return Dec(day=self.dote + other)

        return self

    def __sub__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote - other.dote)
        return Dec(day=self.dote - other)

    def __mul__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote * other.dote)
        return Dec(day=self.dote * other)

    def __truediv__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote / other.dote)
        return Dec(day=self.dote / other)

    def __divmod__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote.__divmod__(other.dote))
        return Dec(day=self.dote.__divmod__(other))

    def __mod__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote % other.dote)
        return Dec(day=self.dote % other)

    def __floordiv__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote // other.dote)
        return Dec(day=self.dote // other)

    def __pow__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote**other.dote)
        return Dec(day=self.dote**other)

    def __matmul__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote @ other.dote)
        return Dec(day=self.dote @ other)

    def __radd__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote + other.dote)
        return Dec(day=self.dote + other)

    def __rsub__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote - self.dote)
        return Dec(day=self.dote - other)

    def __rmul__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote * other.dote)
        return Dec(day=self.dote * other)

    def __rtruediv__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote / self.dote)
        return Dec(day=other / self.dote)

    def __rmod__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote % self.dote)
        return Dec(day=other % self.dote)

    def __rfloordiv__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote // self.dote)
        return Dec(day=other // self.dote)

    def __rpow__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote**self.dote)
        return Dec(day=other**self.dote)

    def __rmatmul__(self, other):
        if isinstance(other, Dec):
            return Dec(day=other.dote @ self.dote)
        return Dec(day=other @ self.dote)

    def __and__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote & other.dote)
        return Dec(day=self.dote & other)

    def __or__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote | other.dote)
        return Dec(day=self.dote | other)

    def __xor__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote ^ other.dote)
        return Dec(day=self.dote ^ other)

    def __rshift__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote >> other.dote)
        return Dec(day=self.dote >> other)

    def __lshift__(self, other):
        if isinstance(other, Dec):
            return Dec(day=self.dote << other.dote)
        return Dec(day=self.dote << other)

    def _flatten(self, nested):
        for i in nested:
            if isinstance(i, (list, tuple)):
                yield from self._flatten(i)
            else:
                yield i

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._range)
        except StopIteration:
            self._create_range()
            raise

    def _generate(self, starts, stop, steps=()):
        """Produce a 2-tuple or list of Dec objects.
        Initialize a list of starts with the provided start.
        """
        steps = tuple(self._flatten(steps))
        for start in starts:
            if not steps:
                # Create an interval
                if type(stop) in (int, float):
                    yield start, start + stop
                else:
                    yield start, stop
            else:
                if type(stop) == int:
                    for i in range(stop):
                        yield start
                        start += steps[i % len(steps)]
                else:
                    total = sum(steps) if steps else 0
                    if total == 0:
                        for s in steps:
                            yield start
                            start += s
                    else:
                        c = 0
                        stop = start + stop if type(stop) == float else stop
                        while (total > 0 and start < stop) or (
                            total < 0 and start > stop
                        ):
                            yield start
                            start += steps[c % len(steps)]
                            c += 1

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    d = Dec(year=2000, day=-1, zone=0)