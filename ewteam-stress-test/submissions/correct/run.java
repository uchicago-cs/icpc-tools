
public class run {

    public static void main(String[] args) throws java.io.IOException
    {
        int c;
        int nlines = 0;

       while ((c = System.in.read()) != -1)
            if(c == '\n')
                nlines++;

        System.out.println(nlines);
    }
}
