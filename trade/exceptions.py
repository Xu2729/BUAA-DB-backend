class InvalidFilterException(Exception):
    def __init__(self):
        Exception.__init__(self)
        self.msg = "不合法的filter"

    def __str__(self):
        return self.msg


class InvalidOrderByException(Exception):
    def __init__(self):
        Exception.__init__(self)
        self.msg = "不合法的order by"

    def __str__(self):
        return self.msg
