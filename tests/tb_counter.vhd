library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_counter is
    port (
        clk : in  std_logic;
        rst : in  std_logic;
        q   : out std_logic_vector(7 downto 0)
    );
end tb_counter;

architecture rtl of tb_counter is
    signal cnt : unsigned(7 downto 0) := (others => '0');
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                cnt <= (others => '0');
            else
                cnt <= cnt + 1;
            end if;
        end if;
    end process;
    q <= std_logic_vector(cnt);
end rtl;
