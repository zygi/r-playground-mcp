PROMPT_REVIEW_PAPER = """\
You will be given a paper to review. Your goal is to analyze its methods in terms of its use of statistical methods. 
If a paper wasn't attached, inform the user and stop - don't make one up.

To analyze the paper, you can use the `execute_r_command` tool. You should recompute and verify the numerical results of the paper.
If the matches are perfect, great. If the matches are not perfect, try to understand whether that can be explained by different assumptions unreported in the paper.
If you're convinced you found a mistake, report that.

Once you're done analyzing the paper, output a summary of its core hypotheses supported by quantitative claims, and your evaluation of the correctness of statistical evaluations.

Guidelines:
- Do not make up synthetic data. You should only use inputs that are explicitly reported in the paper. If the paper does not report enough inputs to do any meaningful checking, just mention that.
"""
