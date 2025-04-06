class EventsException(Exception):
    """
    Custom exception for the Events system.
    Raised when an undeclared or invalid event is accessed or used.
    """
    pass


class Events:
    """
    A dynamic and introspective event handling system.

    Purpose:
    --------
    The `Events` class acts as a container for event slots, allowing dynamic
    creation and subscription to events, mimicking natural Python usage.

    Key Features:
    -------------
    - Automatically adds new event slots as attributes on access.
    - Optional declaration of allowed events via `__events__` for validation.
    - Encapsulates event introspection (listing, iterating).
    - Simplifies syntax: `object.OnChange += callback` without explicit setup.

    Example:
    --------
        e = Events(['on_update'])
        e.on_update += lambda: print("Updated!")
        e.on_update()  # Triggers the event and calls the lambda
    """

    def __init__(self, events=None):
        """
        Initializes the Events container with an optional list of allowed event names.

        :param events: Optional iterable of event names to declare valid events.
        """
        if events is not None:
            try:
                iter(events)  # Validate the iterable
            except Exception:
                raise AttributeError("type object %s is not iterable" % type(events))
            else:
                self.__events__ = events  # Save declared events for validation

    def __getattr__(self, name):
        """
        Handles dynamic attribute access, lazily creating event slots as needed.

        :param name: The name of the event being accessed.
        :return: A new or existing _EventSlot object.
        :raises EventsException: If the event is not declared in __events__.
        """
        # Prevent dynamic creation of special attributes
        if name.startswith('__'):
            raise AttributeError("type object '%s' has no attribute '%s'" %
                                 (self.__class__.__name__, name))

        # Validate event name against declared instance-level events
        if hasattr(self, '__events__'):
            if name not in self.__events__:
                raise EventsException("Event '%s' is not declared" % name)

        # Validate event name against declared class-level events
        elif hasattr(self.__class__, '__events__'):
            if name not in self.__class__.__events__:
                raise EventsException("Event '%s' is not declared" % name)

        # Create and store a new event slot dynamically
        self.__dict__[name] = ev = _EventSlot(name)
        return ev

    def __repr__(self):
        """
        Return a string representation of the Events object.
        """
        return '<%s.%s object at %s>' % (self.__class__.__module__,
                                         self.__class__.__name__,
                                         hex(id(self)))

    __str__ = __repr__  # For readable str() output

    def __len__(self):
        """
        Return the number of event slots created.
        """
        return len(self.__dict__.items())

    def __iter__(self):
        """
        Yield all event slot instances created so far.
        """

        def gen(dictitems=self.__dict__.items()):
            for attr, val in dictitems:
                if isinstance(val, _EventSlot):
                    yield val

        return gen()


class _EventSlot:
    """
    Represents a single event slot that can have multiple subscribers.

    Features:
    ---------
    - Can be called like a function to fire the event.
    - Supports += and -= for adding/removing callbacks.
    - Iterable and indexable like a list of callbacks.
    """

    def __init__(self, name):
        """
        Initialize the event slot with a given name.
        """
        self.targets = []  # List of subscribed callables
        self.__name__ = name  # Name of the event

    def __repr__(self):
        """
        Return a string representation of the event slot.
        """
        return "event '%s'" % self.__name__

    def __call__(self, *a, **kw):
        """
        Fires the event by calling all subscribed targets with arguments.
        """
        for f in tuple(self.targets):  # Use a copy in case targets mutate during call
            f(*a, **kw)

    def __iadd__(self, f):
        """
        Add a new callback to the event using += operator.
        """
        self.targets.append(f)
        return self

    def __isub__(self, f):
        """
        Remove a callback from the event using -= operator.
        Removes all occurrences of the function.
        """
        while f in self.targets:
            self.targets.remove(f)
        return self

    def __len__(self):
        """
        Return the number of subscribers.
        """
        return len(self.targets)

    def __iter__(self):
        """
        Iterate over subscribed callbacks.
        """

        def gen():
            for target in self.targets:
                yield target

        return gen()

    def __getitem__(self, key):
        """
        Allow indexing into the targets list.
        """
        return self.targets[key]
