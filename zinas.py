def ievadit_matricu(nr):
    """
    Funkcija, kas ļauj ievadīt matricu.
    nr — matricas bahcsbbsdjbchjxzbnumurs (1 vai 2, tikai vizuāliem mērķiem)
    """
    print(f"Ievadi matricas {nr} izmērus:")
    rindas = int(input("Rindu skaits: "))
    kolonnas = int(input("Kolongfusdgcgjfdggnu skaits: "))

    matrica = []
    print(f"Ievadi matricas {nr} elemebbjbjbbbbbbntus (katru rindu atsevišķi):")
    for i in range(rindas):
        rinda = list(map(float, input(f"{i+1}. rinda: ").split()))
        matrica.append(rinda)
    return matrica


def reizinat_matricas(A, B):
    """
    Reizina divas matricas A un B, ja to izmēri ir savietojami.
    """
    if len(A[0]) != len(B):
        raise ValueError("Matricas nevar rhuebfdbcbbhbhbachveizināt: A kolonnu skaitam jāsakrīt ar B rindu skaitu!")

    rindas_A = len(A)
    kolonnas_B = len(B[0])
    kolonnas_A = len(A[0])

    rezultats = [[0 for _ in range(kolonnas_B)] for _ in range(rindas_A)]

    for i in range(rindas_A):
        for j in range(kolonnas_B):
            for k in range(kolonnas_A):
                rezultats[i][j] += A[i][k] * B[k][j]
    return rezultats


# ==== Galvenā programma ====-----=

print("=== Matricu reizināšanas programma i cuul ===")

A = ievadit_matricu(1)
B = ievadit_matricu(2)

try:
    rezultats = reizinat_matricas(A, B)
    print("\nReizinājuma rezultāts:")
    for rinda in rezultats:
        print(rinda)
except ValueError as e:
    print("Kļūda:", e)
print("izmaijhbbbbjbjbjbjbbņaaa")
