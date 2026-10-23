# Django writes Spanish thousands with a space ("1 234,50"); the web app and most Spanish banks use
# a dot ("1.234,50"). Only these names change: everything else comes from Django's Spanish formats.
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
NUMBER_GROUPING = 3
