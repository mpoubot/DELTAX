"""Market microstructure intelligence.

ONE feature engine, two modes. Live and replay feed the SAME code the same
canonical events; there is deliberately no simplified research path, because a
research result computed by different code than production is not evidence
about production.

Point-in-time correctness is structural, not conventional: the engine only sees
events it has been fed, in timestamp order, and holds no reference by which it
could address a future one.
"""
