#include <stdio.h>

int main()
{
    char c;
    int nlines = 0;

    while ((c = getchar ()) !=EOF)
        if(c == '\n')
            nlines++;

    printf("%i\n", nlines);

    return 0;
}