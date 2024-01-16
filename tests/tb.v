module tb(
    input clk, 
    output out, 
    input [99:0] vec_in, 
    output [99:0] vec_out
    );
    
    assign out = clk;
    assign vec_out = vec_in;

    initial begin
        $dumpfile("test.vcd");
        $dumpvars(0);
    end

endmodule
