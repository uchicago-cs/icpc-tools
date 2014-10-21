#include <iostream>
using namespace std;

int main()
{
    char c;
    int nlines = 0;

    while (cin.get(c))
        if(c == '\n')
            nlines++;

    cout << nlines << endl;

    return 0;
}
