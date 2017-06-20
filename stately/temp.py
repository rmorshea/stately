
    # @contextmanager
    # def staged_execution(self, *include):
    #     with self.intercepted_stages(*include) as stages:
    #         yield
    #     for s in stages:
    #         # an error at any stage will prevent all
    #         # those following it from being executed
    #         pass

    # @contextmanager
    # def intercepted_stages(self, *include):

    #     def is_parent(cls, cls_or_tuple):
    #         if isinstance(cls_or_tuple, tuple):
    #             cls_or_tuple = (cls_or_tuple,)
    #         for c in cls_or_tuple:
    #             if not issubclass(cls, c):
    #                 return False
    #         else:
    #             return True

    #     def yield_stage(event, status):
    #         return is_parent(type(event), include) and status != event.status

    #     with self.intercepted_events(*include) as events:
    #         def staging(events):
    #             yield list(events)
    #             generators = [e(self) for e in events]
    #             while len(events):
    #                 result = []
    #                 for i in range(len(generators)):
    #                     g = generators[len(result)]
    #                     e = events[len(result)]
    #                     try:
    #                         status = e.status
    #                         while not yield_stage(e, status):
    #                             next(g)
    #                     except StopIteration:
    #                         del generators[len(result)]
    #                         del events[len(result)]
    #                     else:
    #                         result.append(dict(e))
    #                 if result:
    #                     yield result
    #         yield staging(events)