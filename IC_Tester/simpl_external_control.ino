#define F_CPU 16000000UL        // define the clock frequency as 16MHz
#define BAUD 2000000

#include <Arduino.h>
#include <util/setbaud.h>      // Set up the Uart baud rate generator
#define bufRead(addr)      (*(unsigned char *)(addr))
#define bufWrite(addr, b)   (*(unsigned char *)(addr) = (b))
char u_getchar(void);
static void printlong(unsigned long num);

// This character array is used to hold the User's word definitions

char array[28][64]  = {                            // Define a 26 x 48 array for the colon definitions
                         {"6d40{h1106ul1106u}"},  // Musical tones A - G
                         {"6d45{h986ul986u}"},
                         {"6d51{h929ul929u}"},
                         {"6d57{h825ul825u}"},
                         {"6d64{h733ul733u}"},
                         {"6d72{h690ul691u}"},
                         {"6d81{h613ul613u}"},
                         {"_Hello World, and welcome to SIMPL_"},
                         {"5{ABC}"},
                         {""},
                         {""},
                         {""},
                         {"_This is a test message - about 48 characters_"}
                         };



    int a = 0;          // integer variables a,b,c,d
    int b = 0;
    int c = 0;
    int d = 6;          // d is used to denote the digital port pin for I/O operations
//  int d =13;          // d is used to denote the digital port pin for I/O operations Pin 13 on Arduino

   int x = 0;    // Three gen purpose variables
   int y = 0;
    unsigned int z = 0;

    unsigned char in_byte;

    int len = 255;        // the max length of a User word

    long old_millis=0;
    long new_millis=0;




    char name;

    char bite;

    char* parray;

    char buf[256];

    char* addr;

    unsigned int num = 0;
    unsigned int num_val = 0;
    int j;
    char num_buf[11];            // long enough to hold a 32 bit long
    int decade = 0;
    char digit = 0;

void SIMPL_init()
{
    uart_init();

    Serial.write("SIMPL Ready\r\n");
}

// -----------------------------------------------------------------------------------

void SIMPL_run()
{
  while(1)
  {
    txtRead(buf, 255);      // Get the next "instruction" character from the buffer
    txtChk(buf);           // check if it is a : character for beginning a colon definition
    txtEval(buf);          // evaluate and execute the instruction

    u_putchar('\n');  
  }
}

// ---------------------------------------------------------------------------------------------------------
// Functions

void txtRead (char *p, byte n)
{
  byte i = 0;
  while (i < (n-1)) {
//    while (!Serial.available());
    char ch = u_getchar();                    // get the character from the buffer
    if (ch == '\r' || ch == '\n')
    break;
    if (ch >= ' ' && ch <= '~') {
      *p++ = ch;
      i++;
    }
  }
  *p = 0;
}

// ---------------------------------------------------------------------------------------------------------
void txtChk (char *buf)       // Check if the text starts with a colon and if so store in temp[]
{
  if (*buf == ':')  {
  char ch;
  int i =0;
  while ((ch = *buf++)){

  if (ch == ':') {
  u_putchar(*buf);   // get the name from the first character
  u_putchar(10);
  u_putchar(13);
  name = *buf ;
  buf++;
  }

  bufWrite((parray + (len*(name-65) +i)),*buf);

  i++;

}

 x = 1;

}
}

// ---------------------------------------------------------------------------------------------------------
   void txtEval (char *buf)    // Evaluate the instructiona and jump to the action toutine

   {
   long k = 0;

   char *loop;
   char *start;
   char ch;
   while ((ch = *buf++)) {

    switch (ch) {

// Number Decode

    case '0':
    case '1':
    case '2':
    case '3':
    case '4':
    case '5':
    case '6':
    case '7':
    case '8':
    case '9':
      x = ch - '0';
      while (*buf >= '0' && *buf <= '9') {
        x = x*10 + (*buf++ - '0');
      }
      break;

 //-------------------------------------------------------------------------------
 // User Words

      case 'A':            // Point the interpreter to the array containing the words
      case 'B':
      case 'C':
      case 'D':
      case 'E':
      case 'F':
      case 'G':
      case 'H':
      case 'I':
      case 'J':
      case 'K':
      case 'L':
      case 'M':
      case 'N':
      case 'O':
      case 'P':
      case 'Q':
      case 'R':
      case 'S':
      case 'T':
      case 'U':
      case 'V':
      case 'W':
      case 'X':
      case 'Y':
      case 'Z':

      name = ch - 65;
      addr = parray + (len*name);

      txtEval(addr);
      break;

//----------------------------------------------------------
// Memory Group

      case '!':        y = x;                          break;   // store
      case '@':        x = y;                          break;   // fetch
      case 'r':        bite = bufRead(x);  x = bite;   break;   // read a byte from RAM
      case 'w':        bufWrite(y,x);                  break;   // write a byte to RAM  address in y, data in x

// Arithmetic, Logical & Comparison Group

      case '+':       x = x + y;                break;
      case '-':       x = x - y;                break;
      case '*':       x = x * y;                break;
      case '/':       x = x / y;                break;
      case '%':       x = x % y;                break;
      case 'x':       x = x + 1;                break;
      case 'y':       y = y + 1;                break;
      case '&':       x = x & y;                break;      // Logical AND
      case '|':       x = x | y;                break;      // Logical OR
      case '^':       x = x ^ y;                break;      // Logical XOR
      case '~':       x = !x;                   break;      // Complement x
      case '<':      if(x<y){x=1;} else x=0;    break;      // If x<y x= 1 - can be combined with jump j
      case '>':      if(x>y){x=1;} else x=0;    break;      // If x>y x= 1 - can be combined with jump j
      case 'j':      if(x==1){*buf++;}          break;      // test  if x = 1 and jump next instruction

      case ' ':      k=y; y= x;                 break;      // Transfer x into second variable
      case '$':      x=*(buf-2);                break;      // Load x with the ASCII value of the next character  i.e. 5 = 35H or 53 decimal

// I/O Group

      case 'a':   analogWrite(d,x);              break;
      case 'd':   d = x;                         break;
      case 's':   x = analogRead(x);             break;
      case 'i':   x = digitalRead(d);            break;
      case 'o':   digitalWrite(d, x%2);          break;
      case 'h':   digitalWrite(x, 1);            break;
      case 'l':   digitalWrite(x, 0);            break;
      case 'e':  if (x == 0) {
                pinMode(d, INPUT);
            } else if (x == 1) {
                pinMode(d, OUTPUT);
            } else if (x == 2) {
                pinMode(d, INPUT_PULLUP);
            }
            break;

 // Timing and Delays Group

      case 'm':     delay(x);                    break;
      case 'u':     delayMicroseconds(x);        break;
      case '_':      while ((ch = *buf++) && ch != '_') {u_putchar(ch);} crlf();  break;   // Print out the text string between _text_

      case 'k':      x = k;                      break;

 // Printing Group

      case 'p':      printlong(x);               crlf();      break;       // print integer with crlf
      case 'q':      printlong(x);                            break;       // print integer
      case 'b':      printlong(millis());        crlf();      break;
      case 'c':      printlong(micros());        crlf();      break;
      case 't':      printlong(micros());                     break;


// Looping and program control group

      case '{':      k = x;      loop = buf;      while ((ch = *buf++) && ch != '}') { }
      case '}':      if (k) { k--; buf = loop;}   break;

      case '(':      k = x;  while (k)    {ch = *buf++; if (ch == ','){ k--;} }   break;       //  // Select some code from a list separated by commas eg 5(0p,1p,2p,3p,4p,5p,6p)
      case ',':      k--  ;  while (k<0)  {ch = *buf++; if (ch == ')') {break;} } break;

//----------------------------------------------------------------------------------
// Byte wide output
/*
      case 'n':                  // Output an 8 bit value on I/O Dig 2  - Dig 9
                                 // Can be extended to 12 bits on Dig 2 - Dig 13

      if(x>=128){digitalWrite(9,HIGH); x =  x- 128;} else {digitalWrite(9,LOW);}
      if(x>=64){digitalWrite(8,HIGH); x =  x- 64;} else {digitalWrite(8,LOW);}
      if(x>=32){digitalWrite(7,HIGH); x =  x- 32;} else {digitalWrite(7,LOW);}
      if(x>=16){digitalWrite(6,HIGH); x =  x- 16;} else {digitalWrite(6,LOW);}
      if(x>=8){digitalWrite(5,HIGH); x =  x- 8;} else {digitalWrite(5,LOW);}
      if(x>=4){digitalWrite(4,HIGH); x =  x- 4;} else {digitalWrite(4,LOW);}
      if(x>=2){digitalWrite(3,HIGH); x =  x- 2;} else {digitalWrite(3,LOW);}
      if(x>=1){digitalWrite(2,HIGH); x =  x- 1;} else {digitalWrite(2,LOW);}

      break;
  */

//----------------------------------------------------------------------------------
// Print out the current word list



      case '?':                             // Print out all the RAM
      parray = &array[0][0];                // reset parray to the pointer to the first element

      for (int j = 0; j<26; j++) {

      u_putchar(j+65);                  // print the caps word name
      u_putchar(32);                    // space

      for (int i=0; i<len; i++) {
      in_byte = bufRead( parray +  (j *len )+i);          // read the array
      u_putchar(in_byte);                                 // print the character to the serial port
    }

     crlf();

   }
   for(int i = 0; i <10; i++)      // add some spaces to make it more legible on the page

   {
   crlf();
   }
    break;

//----------------------------------------------------------------------------------------------------
// Added 15-2-2015 - all appears to be working

/*

    case '(':                                     // The start of a condition test
      k = x;
      start = buf;                               // remember the start position of the test
      while ((ch = *buf++) && ch != ')') {       // get the next character into ch and increment the buffer pointer *buf - evaluate the code
      }

     case ')':
    if (x) {                                    // if x is positive - go around again
     buf = start;
    }
      break;

      */
//--------------------------------------------------------------------------------------------------
/*
      case '.':
      while ((ch = *buf++) && ch != '.') {
//        Serial.print(ch);
         name = ch - 65;
         addr = parray + (len*name);
        while ((ch = *addr++) && ch != '.') {
        u_putchar(ch);

      }

      }
      crlf();
      break;

*/

//      txtEval(addr);
//      break;

//--------------------------------------------------------------------------------------
   /*

     case 'z':                                                          // z is a non-blocking pause or nap - measured in "zeconds" which allows UART characters,

     old_millis = millis();                                             // get the millisecond count when you enter the switch-case

 //     while (!Serial.available()||millis()-old_millis<=(x*1000))
 //     { }
      printstring("waiting for escape");

    //  Serial.println("Got a char");

      ch = u_getchar();

       printstring("Got a Â£");

      // Put the idle loop and escape code here
      if(ch=='Â£')
      {
        printstring("Escape");
        break;
      }
                                                                        // interrupts or digital Inputs to break the pause
//       Serial.println(millis());
//       break;


*/
//--------------------------------------------------------------------------------------

    }   // End of switch


  }   // end of textEval



//--------------------------------------------------------------------------------------
/*
 if(*buf == 0)
 {
  u_putchar(32);
  u_putchar(111);      //ok followed by crlf
  u_putchar(107);
  u_putchar(10);
  u_putchar(13);
 }*/



   }      //ok

//--------------------------------------------------------------------------------------
// UART Routines
//--------------------------------------------------------------------------------------

void uart_init(void)
{
    UBRR0H = UBRRH_VALUE;
    UBRR0L = UBRRL_VALUE;

#if USE_2X
    UCSR0A |= _BV(U2X0);
#else
    UCSR0A &= ~(_BV(U2X0));
#endif

    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00); /* 8-bit data */
    UCSR0B = _BV(RXEN0) | _BV(TXEN0);   /* Enable RX and TX */
}

void u_putchar(char c) {
    loop_until_bit_is_set(UCSR0A, UDRE0); /* Wait until data register empty. */
    UDR0 = c;
}

char u_getchar(void) {
    loop_until_bit_is_set(UCSR0A, RXC0); /* Wait until data exists. */
    return UDR0;
}


//----------------------------------------------------------------------------------------------------------
// Print a string
void printstring(char *buf)
{

}

//----------------------------------------------------------------------------------------------------------
// Print a CR-LF

  void crlf(void)                  // send a crlf
  {
  u_putchar(10);
  u_putchar(13);
  }

 //---------------------------------------------------------------------------------------------------------
 // Print a 32 bit integer

static void printlong(unsigned long num) {
  if (num / (unsigned long)10 != 0) printlong(num / (unsigned long)10);
  u_putchar((char)(num % (unsigned long)10) + '0');

  return;

  //crlf();
}



 //------------------------------------That's All Folks!-------------------------------------
