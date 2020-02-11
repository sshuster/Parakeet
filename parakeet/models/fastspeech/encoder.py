import paddle.fluid.dygraph as dg
import paddle.fluid as fluid
from parakeet.modules.utils import *
from parakeet.models.fastspeech.FFTBlock import FFTBlock

class Encoder(dg.Layer):
    def __init__(self,
                 n_src_vocab,
                 len_max_seq,
                 n_layers,
                 n_head,
                 d_k,
                 d_v,
                 d_model,
                 d_inner,
                 fft_conv1d_kernel,
                 fft_conv1d_padding,
                 dropout=0.1):
        super(Encoder, self).__init__()
        n_position = len_max_seq + 1

        self.src_word_emb = dg.Embedding(size=[n_src_vocab, d_model], padding_idx=0)
        self.pos_inp = get_sinusoid_encoding_table(n_position, d_model, padding_idx=0)
        self.position_enc = dg.Embedding(size=[n_position, d_model],
                                 padding_idx=0,
                                 param_attr=fluid.ParamAttr(
                                     initializer=fluid.initializer.NumpyArrayInitializer(self.pos_inp),
                                     trainable=False))
        self.layer_stack = [FFTBlock(d_model, d_inner, n_head, d_k, d_v, fft_conv1d_kernel, fft_conv1d_padding, dropout=dropout) for _ in range(n_layers)]
        for i, layer in enumerate(self.layer_stack):
            self.add_sublayer('fft_{}'.format(i), layer)

    def forward(self, character, text_pos):
        """
        Encoder layer of FastSpeech.
        
        Args:
            character (Variable): Shape(B, T_text), dtype: float32. The input text
                characters. T_text means the timesteps of input characters.
            text_pos (Variable): Shape(B, T_text), dtype: int64. The input text
                position. T_text means the timesteps of input characters.

        Returns:
            enc_output (Variable), Shape(B, text_T, C), the encoder output.
            non_pad_mask (Variable), Shape(B, T_text, 1), the mask with non pad.
            enc_slf_attn_list (list<Variable>), Len(n_layers), Shape(B * n_head, text_T, text_T), the encoder self attention list.
        """
        enc_slf_attn_list = []
        # -- prepare masks
        # shape character (N, T)
        slf_attn_mask = get_attn_key_pad_mask(seq_k=character, seq_q=character)
        non_pad_mask = get_non_pad_mask(character)

        # -- Forward
        enc_output = self.src_word_emb(character) + self.position_enc(text_pos) #(N, T, C)

        for enc_layer in self.layer_stack:
            enc_output, enc_slf_attn = enc_layer(
                enc_output,
                non_pad_mask=non_pad_mask,
                slf_attn_mask=slf_attn_mask)
            enc_slf_attn_list += [enc_slf_attn]
        
        return enc_output, non_pad_mask, enc_slf_attn_list